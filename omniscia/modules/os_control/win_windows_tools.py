"""Tools de janela (Windows).

Expõe utilitários de focar/restaurar janelas por título e inventariar janelas abertas.
"""

from __future__ import annotations

import json
from typing import Any

from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult
from omniscia.modules.os_control.win_windows import (
    focus_window_by_title_contains,
    get_foreground_window_title,
    list_top_level_windows,
)


def register_windows_window_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="win.focus_window",
            description="Foca/restaura uma janela do Windows por substring do título e retorna seu retângulo.",
            risk="HIGH",
            fn=_win_focus_window,
        )
    )

    registry.register(
        ToolSpec(
            name="win.list_windows",
            description=(
                "Lista janelas top-level abertas (título/pid/retângulo). "
                "Args: title_contains?, visible_only?, include_empty_titles?, max_results?"
            ),
            risk="LOW",
            fn=_win_list_windows,
        )
    )

    registry.register(
        ToolSpec(
            name="win.foreground_window",
            description="Retorna o título da janela atualmente em foco (Windows).",
            risk="LOW",
            fn=_win_foreground_window,
        )
    )


def _win_focus_window(args: dict[str, Any]) -> ToolResult:
    title_contains = str(args.get("title_contains", "") or "").strip()
    timeout_s = float(args.get("timeout_s", 2.5) or 2.5)
    visible_only = bool(args.get("visible_only", True))

    if not title_contains:
        return ToolResult(status="error", error="title_contains vazio")

    rect = focus_window_by_title_contains(title_contains, timeout_s=timeout_s, visible_only=visible_only)
    if not rect:
        return ToolResult(status="error", error="janela não encontrada")

    return ToolResult(status="ok", output=json.dumps({"title_contains": title_contains, "rect": rect}, ensure_ascii=False))


def _win_list_windows(args: dict[str, Any]) -> ToolResult:
    title_contains = str(args.get("title_contains", "") or "").strip() or None
    visible_only = bool(args.get("visible_only", True))
    include_empty_titles = bool(args.get("include_empty_titles", False))
    max_results = int(args.get("max_results", 200) or 200)

    wins = list_top_level_windows(
        title_contains=title_contains,
        visible_only=visible_only,
        include_empty_titles=include_empty_titles,
        max_results=max_results,
    )
    payload = {
        "title_contains": title_contains,
        "visible_only": visible_only,
        "count": len(wins),
        "windows": wins,
    }
    return ToolResult(status="ok", output=json.dumps(payload, ensure_ascii=False))


def _win_foreground_window(args: dict[str, Any]) -> ToolResult:
    title = (get_foreground_window_title() or "").strip()
    if not title:
        return ToolResult(status="ok", output=json.dumps({"title": None}, ensure_ascii=False))
    return ToolResult(status="ok", output=json.dumps({"title": title}, ensure_ascii=False))
