"""Ferramentas (tools) de memória.

Rationale:
- Expor memória como tool permite que o router (heurístico ou LLM) a use quando precisar.
- Mantemos o core desacoplado de como a memória é implementada.
"""

from __future__ import annotations

from typing import Any

from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult
from omniscia.modules.memory.store import JsonlMemoryStore


def register_memory_tools(registry: ToolRegistry, store: JsonlMemoryStore) -> None:
    registry.register(
        ToolSpec(
            name="memory.search",
            description="Busca na memória persistente (baseline substring)",
            risk="LOW",
            fn=lambda args: _memory_search(args, store=store),
        )
    )

    registry.register(
        ToolSpec(
            name="memory.recent",
            description="Mostra eventos mais recentes da memória (timeline) sem query",
            risk="LOW",
            fn=lambda args: _memory_recent(args, store=store),
        )
    )


def _memory_search(args: dict[str, Any], *, store: JsonlMemoryStore) -> ToolResult:
    query = str(args.get("query", "")).strip()
    limit = int(args.get("limit", 5) or 5)

    events = store.search_text(query, limit=limit)

    # Formatação compacta para caber bem no terminal.
    out_lines: list[str] = []
    for ev in events:
        out_lines.append(f"[{ev.kind}] {ev.payload}")

    return ToolResult(status="ok", output="\n".join(out_lines) if out_lines else "(sem resultados)")


def _memory_recent(args: dict[str, Any], *, store: JsonlMemoryStore) -> ToolResult:
    limit = int(args.get("limit", 20) or 20)
    events = store.recent(limit=limit)

    out_lines: list[str] = []
    for ev in events:
        out_lines.append(f"[{ev.kind}] {ev.payload}")

    return ToolResult(status="ok", output="\n".join(out_lines) if out_lines else "(sem eventos)")
