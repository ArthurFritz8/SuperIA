"""RAG invertido para tools: shortlist semântico (ChromaDB) — opt-in.

Objetivo:
- Selecionar Top-K tools relevantes para injetar no prompt do router LLM.
- Reduz tokens e melhora qualidade do plano quando há muitas tools.

Como funciona:
- Indexa cada tool (nome + descrição + risco) como um documento.
- Faz query com o texto do usuário e retorna os tool names mais próximos.

Segurança:
- Local-only (ChromaDB persistente). Se deps faltarem, cai para heurística lexical.
"""

from __future__ import annotations

import os
import threading
import time
import hashlib
from dataclasses import dataclass

from omniscia.core.tools import ToolRegistry


@dataclass(frozen=True)
class ToolHit:
    name: str
    score: float


class ToolSemanticShortlister:
    def __init__(
        self,
        *,
        persist_dir: str = "data/chroma_tools",
        collection: str = "omniscia_tools",
        embed_model: str = "all-MiniLM-L6-v2",
    ) -> None:
        from omniscia.modules.memory.vector_store import ChromaVectorMemory

        self._vm = ChromaVectorMemory(persist_dir=persist_dir, collection=collection, embed_model=embed_model)
        self._lock = threading.Lock()
        self._indexed_fingerprint: str | None = None
        self._shortlist_cache: dict[tuple[str, int, str], tuple[float, list[ToolHit]]] = {}
        self._shortlist_ttl_s: float = 180.0
        self._last_index_at: float = 0.0
        self._min_index_interval_s: float = 5.0

    def _fingerprint_registry(self, registry: ToolRegistry) -> str:
        """Fingerprint estável baseado em (name, risk, description).

        Evita reindexar em cada chamada e detecta alterações reais no catálogo.
        """

        try:
            items: list[str] = []
            for t in registry.list():
                name = (getattr(t, "name", "") or "").strip()
                if not name:
                    continue
                risk = (getattr(t, "risk", "") or "").strip()
                desc = (getattr(t, "description", "") or "").strip()
                items.append(name + "\n" + risk + "\n" + desc)
            items.sort()
            payload = "\n\n".join(items).encode("utf-8", errors="ignore")
            return hashlib.sha256(payload).hexdigest()[:16]
        except Exception:
            return "?"

    def _cache_get(self, key: tuple[str, int, str]) -> list[ToolHit] | None:
        now = time.time()
        hit = self._shortlist_cache.get(key)
        if not hit:
            return None
        ts, data = hit
        if (now - float(ts)) > self._shortlist_ttl_s:
            try:
                self._shortlist_cache.pop(key, None)
            except Exception:
                pass
            return None
        return list(data)

    def _cache_put(self, key: tuple[str, int, str], val: list[ToolHit]) -> None:
        try:
            self._shortlist_cache[key] = (time.time(), list(val))
            if len(self._shortlist_cache) > 512:
                # prune cheap: remove ~oldest 1/4
                items = sorted(self._shortlist_cache.items(), key=lambda kv: kv[1][0])
                for k, _ in items[: max(1, len(items) // 4)]:
                    self._shortlist_cache.pop(k, None)
        except Exception:
            pass

    def ensure_indexed(self, *, registry: ToolRegistry) -> None:
        fp = self._fingerprint_registry(registry)
        if fp == self._indexed_fingerprint:
            return

        now = time.time()
        if self._last_index_at and (now - self._last_index_at) < self._min_index_interval_s:
            return

        with self._lock:
            # Re-check under lock
            if fp == self._indexed_fingerprint:
                return
            self._last_index_at = now

            # Prune tools removidas (best-effort)
            try:
                current_names = {
                    (getattr(t, "name", "") or "").strip() for t in registry.list() if (getattr(t, "name", "") or "").strip()
                }
                # vector store expõe listagem via ids (quando disponível)
                existing = set(self._vm.list_ids())  # type: ignore[attr-defined]
                for stale in (existing - current_names):
                    try:
                        self._vm.delete(item_id=stale)
                    except Exception:
                        pass
            except Exception:
                pass

            for t in registry.list():
                name = (getattr(t, "name", "") or "").strip()
                if not name:
                    continue
                desc = (getattr(t, "description", "") or "").strip()
                risk = (getattr(t, "risk", "") or "").strip()
                doc = f"tool: {name}\nRISK: {risk}\nDESC: {desc}\n"
                # ID estável = nome da tool
                self._vm.upsert(item_id=name, text=doc, meta={"name": name, "risk": risk})
            self._indexed_fingerprint = fp
            # Cache muda quando o catálogo muda
            self._shortlist_cache.clear()

    def shortlist(self, *, registry: ToolRegistry, query: str, k: int) -> list[ToolHit]:
        if k < 1:
            k = 1
        if k > 40:
            k = 40
        fp = self._fingerprint_registry(registry)
        q = str(query or "").strip()
        cache_key = (q, int(k), fp)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        self.ensure_indexed(registry=registry)
        hits = self._vm.query(query=query, limit=k)
        out: list[ToolHit] = []
        for h in hits:
            name = str((h.meta or {}).get("name") or h.id or "").strip()
            if not name:
                continue
            out.append(ToolHit(name=name, score=float(h.score)))
        self._cache_put(cache_key, out)
        return out


def build_shortlister_from_env() -> ToolSemanticShortlister | None:
    if os.getenv("OMNI_ROUTER_TOOL_RAG", "false").strip().lower() != "true":
        return None

    persist_dir = (os.getenv("OMNI_ROUTER_TOOL_RAG_DIR", "data/chroma_tools") or "").strip() or "data/chroma_tools"
    collection = (os.getenv("OMNI_ROUTER_TOOL_RAG_COLLECTION", "omniscia_tools") or "").strip() or "omniscia_tools"
    embed_model = (os.getenv("OMNI_ROUTER_TOOL_RAG_EMBED_MODEL", "all-MiniLM-L6-v2") or "").strip() or "all-MiniLM-L6-v2"

    try:
        return ToolSemanticShortlister(persist_dir=persist_dir, collection=collection, embed_model=embed_model)
    except Exception:
        return None
