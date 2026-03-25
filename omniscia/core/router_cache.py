"""Cache persistente de roteamento (SQLite) — opt-in.

Objetivo:
- Evitar recomputar planos do router LLM para prompts idênticos.
- Reduz latência e custo de tokens em rotas repetidas.

Notas:
- Cache é melhor-effort: falhas não quebram o agente.
- Guardamos apenas o *plano final* (JSON) já validado.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from omniscia.core.types import Plan


class RouterPlanCache:
    def __init__(self, *, path: str, ttl_s: float) -> None:
        self._path = str(path)
        self._ttl_s = float(ttl_s)
        self._lock = threading.Lock()

        # Observabilidade leve (best-effort). Não é thread-safe estrito, mas é protegido por lock.
        self._stats = {
            "get_calls": 0,
            "get_hit": 0,
            "get_miss": 0,
            "get_expired": 0,
            "put_calls": 0,
            "prune_calls": 0,
            "pruned_expired": 0,
            "pruned_oversize": 0,
        }

        self._last_prune_at = 0.0
        self._logger = logging.getLogger(__name__)

        p = Path(self._path)
        p.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS router_plan_cache (
                    k TEXT PRIMARY KEY,
                    plan_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_router_plan_cache_created ON router_plan_cache(created_at)")
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=2.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def get(self, key: str) -> Plan | None:
        if not key:
            return None
        now = time.time()
        with self._lock:
            self._stats["get_calls"] += 1
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT plan_json, created_at FROM router_plan_cache WHERE k = ?",
                    (key,),
                ).fetchone()

                if not row:
                    self._stats["get_miss"] += 1
                    return None

                plan_json, created_at = row
                if self._ttl_s > 0 and (now - float(created_at)) > self._ttl_s:
                    self._stats["get_expired"] += 1
                    try:
                        conn.execute("DELETE FROM router_plan_cache WHERE k = ?", (key,))
                        conn.commit()
                    except Exception:
                        pass
                    return None

                self._stats["get_hit"] += 1

        try:
            data: Any = json.loads(str(plan_json))
            return Plan.model_validate(data)
        except Exception:
            return None

    def put(self, key: str, plan: Plan) -> None:
        if not key:
            return
        try:
            payload = plan.model_dump(mode="json")
            plan_json = json.dumps(payload, ensure_ascii=False)
        except Exception:
            return

        with self._lock:
            self._stats["put_calls"] += 1
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO router_plan_cache (k, plan_json, created_at) VALUES (?, ?, ?)",
                    (key, plan_json, time.time()),
                )
                conn.commit()

    def prune(self, *, keep_last_n: int = 5000) -> None:
        if keep_last_n < 1:
            keep_last_n = 1
        with self._lock:
            self._stats["prune_calls"] += 1
            with self._connect() as conn:
                # Remove tudo exceto os mais recentes.
                conn.execute(
                    """
                    DELETE FROM router_plan_cache
                    WHERE k IN (
                        SELECT k FROM router_plan_cache
                        ORDER BY created_at DESC
                        LIMIT -1 OFFSET ?
                    )
                    """,
                    (int(keep_last_n),),
                )
                conn.commit()

    def prune_expired(self) -> int:
        """Remove entradas expiradas por TTL. Retorna quantidade removida (best-effort)."""

        if self._ttl_s <= 0:
            return 0

        cutoff = time.time() - float(self._ttl_s)
        removed = 0
        with self._lock:
            with self._connect() as conn:
                try:
                    cur = conn.execute(
                        "DELETE FROM router_plan_cache WHERE created_at < ?",
                        (float(cutoff),),
                    )
                    removed = int(getattr(cur, "rowcount", 0) or 0)
                    conn.commit()
                except Exception:
                    return 0
        if removed:
            with self._lock:
                self._stats["pruned_expired"] += removed
        return removed

    def maybe_maintain(self, *, keep_last_n: int = 5000, min_interval_s: float = 300.0) -> None:
        """Manutenção best-effort para limitar crescimento do DB.

        - Remove expirados (TTL)
        - Mantém somente os últimos N
        - Rate-limited por `min_interval_s`
        """

        try:
            now = time.time()
            with self._lock:
                if (now - float(self._last_prune_at)) < float(min_interval_s):
                    return
                self._last_prune_at = now

            removed_expired = self.prune_expired()
            if keep_last_n and keep_last_n > 0:
                # oversize pruning (contabilizamos de forma aproximada)
                before = self.size()
                self.prune(keep_last_n=int(keep_last_n))
                after = self.size()
                delta = max(0, int(before - after))
                if delta:
                    with self._lock:
                        self._stats["pruned_oversize"] += delta

            if removed_expired or (keep_last_n and keep_last_n > 0):
                self._logger.debug(
                    "router sqlite cache maintenance: removed_expired=%s keep_last_n=%s",
                    removed_expired,
                    keep_last_n,
                )
        except Exception:
            return

    def size(self) -> int:
        """Quantidade de entradas (best-effort)."""

        with self._lock:
            with self._connect() as conn:
                try:
                    row = conn.execute("SELECT COUNT(1) FROM router_plan_cache").fetchone()
                    return int(row[0]) if row else 0
                except Exception:
                    return 0

    def stats(self) -> dict[str, int]:
        """Snapshot de contadores internos (best-effort)."""

        with self._lock:
            return dict(self._stats)


def make_cache_key_namespace(
    *,
    provider: str,
    model: str,
    base_url: str,
    registry_fingerprint: str,
    schema_version: str = "v2",
) -> str:
    """Namespace estável para evitar colisões entre configs/versões.

    Mantemos curto e determinístico para uso como prefixo na key.
    """

    p = (provider or "").strip().lower()
    m = (model or "").strip()
    b = (base_url or "").strip()
    rf = (registry_fingerprint or "").strip()
    return "|".join(["router", str(schema_version), p, m, b, rf])


def build_router_cache_from_env() -> RouterPlanCache | None:
    # Cache persistente deve ser opt-in; além disso, desabilitamos em pytest
    # para manter os testes determinísticos (evita hits em cache entre execuções).
    if os.getenv("PYTEST_CURRENT_TEST"):
        return None

    if os.getenv("OMNI_ROUTER_SQLITE_CACHE", "false").strip().lower() != "true":
        return None

    path = (os.getenv("OMNI_ROUTER_SQLITE_CACHE_PATH", "data/router_cache.sqlite") or "").strip()
    if not path:
        return None

    ttl_s = float(os.getenv("OMNI_ROUTER_SQLITE_CACHE_TTL_S", "86400") or "86400")
    try:
        return RouterPlanCache(path=path, ttl_s=ttl_s)
    except Exception:
        return None
