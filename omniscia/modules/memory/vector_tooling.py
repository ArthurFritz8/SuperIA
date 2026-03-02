"""Tools para memória vetorial (ChromaDB) — opt-in.

Ferramentas:
- memory.search_vector: busca semântica
- memory.index_recent: indexa eventos recentes do JSONL

Observação:
- Essas tools só são registradas quando Settings.vector_memory_enabled=true.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from omniscia.core.config import Settings
from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult
from omniscia.modules.memory.store import JsonlMemoryStore
from omniscia.modules.memory.vector_store import ChromaVectorMemory

logger = logging.getLogger(__name__)


def register_vector_memory_tools(
    registry: ToolRegistry,
    *,
    memory_store: JsonlMemoryStore | None,
    settings: Settings,
) -> None:
    vm = ChromaVectorMemory(
        persist_dir="data/chroma",
        collection="omniscia_memory",
        embed_model=("all-MiniLM-L6-v2"),
    )

    registry.register(
        ToolSpec(
            name="memory.search_vector",
            description="Busca semântica na memória vetorial (ChromaDB)",
            risk="LOW",
            fn=lambda args: _search_vector(args, vm=vm),
        )
    )

    registry.register(
        ToolSpec(
            name="memory.index_recent",
            description="Indexa eventos recentes do JSONL na memória vetorial",
            risk="LOW",
            fn=lambda args: _index_recent(args, vm=vm, store=memory_store),
        )
    )

    # Auto-index opcional (best-effort): indexa um pequeno lote recente ao iniciar.
    if settings.vector_memory_auto_index and memory_store is not None:
        try:
            _index_recent({"limit": 60}, vm=vm, store=memory_store)
        except Exception:
            logger.info("Auto-index vetorial falhou (best-effort).")


def _stable_id(kind: str, payload: dict[str, Any]) -> str:
    h = hashlib.sha256()
    h.update((kind or "").encode("utf-8"))
    h.update(b"\n")
    h.update(str(payload).encode("utf-8", errors="ignore"))
    return h.hexdigest()[:24]


def _event_to_text(kind: str, payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    # Texto compacto e útil para embeddings.
    if kind == "user_message":
        t = str((payload or {}).get("text", "") or "").strip()
        return (f"USER: {t}", {"kind": kind})

    if kind == "agent_response":
        t = str((payload or {}).get("text", "") or "").strip()
        return (f"ASSISTANT: {t}", {"kind": kind})

    if kind == "tool_output":
        tool = str((payload or {}).get("tool", "") or "").strip()
        status = str((payload or {}).get("status", "") or "").strip()
        out = str((payload or {}).get("output", "") or "").strip()
        err = str((payload or {}).get("error", "") or "").strip()
        text = f"TOOL_RESULT tool={tool} status={status}"
        if out:
            text += "\nOUTPUT:\n" + out[:2000]
        if err:
            text += "\nERROR:\n" + err[:1000]
        return (text, {"kind": kind, "tool": tool, "status": status})

    # Fallback
    return (f"{kind}: {payload}", {"kind": kind})


def _search_vector(args: dict[str, Any], *, vm: ChromaVectorMemory) -> ToolResult:
    query = str(args.get("query", "") or "").strip()
    limit = int(args.get("limit", 5) or 5)

    hits = vm.query(query=query, limit=limit)
    if not hits:
        return ToolResult(status="ok", output="(sem resultados)")

    lines: list[str] = []
    for h in hits:
        lines.append(f"[{h.score:.3f}] {h.meta.get('kind','')} {h.meta.get('tool','')}")
        t = (h.text or "").strip()
        if len(t) > 500:
            t = t[:500] + "..."
        lines.append(t)
        lines.append("-")

    return ToolResult(status="ok", output="\n".join(lines).strip())


def _index_recent(args: dict[str, Any], *, vm: ChromaVectorMemory, store: JsonlMemoryStore | None) -> ToolResult:
    if store is None:
        return ToolResult(status="error", error="memory_store não disponível")

    limit = int(args.get("limit", 50) or 50)
    if limit < 1:
        limit = 1
    if limit > 200:
        limit = 200

    events = store.recent(limit=limit)
    n = 0
    for ev in events:
        text, meta = _event_to_text(ev.kind, ev.payload)
        if not text.strip():
            continue
        item_id = _stable_id(ev.kind, ev.payload)
        vm.upsert(item_id=item_id, text=text, meta=meta)
        n += 1

    return ToolResult(status="ok", output=f"indexed {n} events")
