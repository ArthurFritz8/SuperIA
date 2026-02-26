"""Tools de janela (Windows).

Expõe utilitários de focar/restaurar janelas por título.
"""

from __future__ import annotations

import json
from typing import Any

from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult
from omniscia.modules.os_control.win_windows import focus_window_by_title_contains


def register_windows_window_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="win.focus_window",
            description="Foca/restaura uma janela do Windows por substring do título e retorna seu retângulo.",
            risk="HIGH",
            fn=_win_focus_window,
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
