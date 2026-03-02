"""Store de memória persistente (JSONL).

Rationale:
- Agentes autônomos precisam de um rastro: "o que foi dito" e "o que foi feito".
- JSONL é simples, barato e legível.

Este store não guarda segredos por padrão.
Se você quiser guardar segredos (senhas/tokens), isso deve passar por um módulo
separado de "secrets" com criptografia e políticas claras.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MemoryEvent:
    ts: float
    kind: str  # ex: user_message | agent_response | tool_output | plan
    payload: dict[str, Any]


class JsonlMemoryStore:
    def __init__(self, *, base_dir: str = "data/memory") -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)
        self._events_path = self._base / "events.jsonl"

    def append(self, kind: str, payload: dict[str, Any]) -> None:
        event = MemoryEvent(ts=time.time(), kind=kind, payload=payload)
        line = json.dumps(
            {"ts": event.ts, "kind": event.kind, "payload": event.payload},
            ensure_ascii=False,
        )
        with self._events_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def search_text(self, query: str, *, limit: int = 5) -> list[MemoryEvent]:
        """Busca simples por substring nos payloads.

        Rationale:
        - Sempre disponível (sem embeddings).
        - Útil como baseline para memória.

        Observação:
        - Não é perfeito. A versão vetorial (RAG) vem depois.
        """

        q = (query or "").strip().lower()
        if not q:
            return []

        results: list[MemoryEvent] = []
        if not self._events_path.exists():
            return []

        # Leitura reversa: traz os eventos mais recentes primeiro.
        lines = self._events_path.read_text(encoding="utf-8").splitlines()
        for line in reversed(lines):
            try:
                obj = json.loads(line)
                payload = obj.get("payload", {})
                hay = json.dumps(payload, ensure_ascii=False).lower()
                if q in hay:
                    results.append(
                        MemoryEvent(ts=float(obj.get("ts", 0.0)), kind=str(obj.get("kind", "")), payload=payload)
                    )
                    if len(results) >= limit:
                        break
            except Exception:
                continue

        return results


    def recent(self, *, limit: int = 20) -> list[MemoryEvent]:
        """Retorna eventos mais recentes.

        Útil para depurar "o que o agente fez" sem precisar formular uma query.
        """

        if limit < 1:
            return []
        if limit > 200:
            limit = 200

        if not self._events_path.exists():
            return []

        lines = self._events_path.read_text(encoding="utf-8").splitlines()
        out: list[MemoryEvent] = []
        for line in reversed(lines):
            try:
                obj = json.loads(line)
                out.append(
                    MemoryEvent(ts=float(obj.get("ts", 0.0)), kind=str(obj.get("kind", "")), payload=obj.get("payload", {}) or {})
                )
                if len(out) >= limit:
                    break
            except Exception:
                continue

        return out
