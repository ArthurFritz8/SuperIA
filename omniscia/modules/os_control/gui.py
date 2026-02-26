"""Automação de GUI (mouse/teclado) via PyAutoGUI.

Rationale:
- PyAutoGUI é simples e cross-platform.
- Para um agente autônomo, GUI é poderosa mas arriscada.

Guardrails deste marco:
- Import lazy: o core não quebra se pyautogui não estiver instalado.
- Validação de coordenadas: exige x/y inteiros e dentro do tamanho da tela.

Política de segurança:
- O router deve marcar ações destrutivas/arriscadas como CRITICAL para passar pelo HITL.
  (ex: clicar, digitar).
"""

from __future__ import annotations

from typing import Any

from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult


def register_gui_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="gui.get_mouse",
            description="Retorna posição atual do mouse",
            risk="LOW",
            fn=_gui_get_mouse,
        )
    )

    registry.register(
        ToolSpec(
            name="gui.move_mouse",
            description="Move o mouse para (x,y)",
            risk="HIGH",
            fn=_gui_move_mouse,
        )
    )

    registry.register(
        ToolSpec(
            name="gui.click",
            description="Clica em (x,y) com botão esquerdo",
            risk="HIGH",
            fn=_gui_click,
        )
    )

    registry.register(
        ToolSpec(
            name="gui.click_box_center",
            description="Clica no centro de uma caixa (x,y,w,h) (útil com screen.find_text)",
            risk="HIGH",
            fn=_gui_click_box_center,
        )
    )

    registry.register(
        ToolSpec(
            name="gui.type_text",
            description="Digita texto no foco atual",
            risk="HIGH",
            fn=_gui_type_text,
        )
    )


def _require_pyautogui():
    try:
        import pyautogui

        # Fail-safe do PyAutoGUI: mover mouse pro canto superior esquerdo aborta.
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.05
        return pyautogui, None
    except Exception as exc:  # noqa: BLE001
        return None, f"pyautogui indisponível: {exc}"


def _screen_size(pyautogui) -> tuple[int, int]:
    w, h = pyautogui.size()
    return int(w), int(h)


def _coerce_xy(args: dict[str, Any], pyautogui) -> tuple[int, int] | None:
    if "x" not in args or "y" not in args:
        return None

    try:
        raw_x = args.get("x")
        raw_y = args.get("y")
        if raw_x is None or raw_y is None:
            return None
        x = int(raw_x)
        y = int(raw_y)
    except Exception:
        return None

    w, h = _screen_size(pyautogui)
    if x < 0 or y < 0 or x >= w or y >= h:
        return None

    return x, y


def _gui_get_mouse(args: dict[str, Any]) -> ToolResult:
    pyautogui, err = _require_pyautogui()
    if pyautogui is None:
        return ToolResult(status="error", error=err)

    x, y = pyautogui.position()
    w, h = _screen_size(pyautogui)
    return ToolResult(status="ok", output=f"mouse=({x},{y}) screen=({w}x{h})")


def _gui_move_mouse(args: dict[str, Any]) -> ToolResult:
    pyautogui, err = _require_pyautogui()
    if pyautogui is None:
        return ToolResult(status="error", error=err)

    xy = _coerce_xy(args, pyautogui)
    if xy is None:
        w, h = _screen_size(pyautogui)
        return ToolResult(status="error", error=f"x/y inválidos (0<=x<{w}, 0<=y<{h})")

    x, y = xy
    pyautogui.moveTo(x, y, duration=0.15)
    return ToolResult(status="ok", output=f"moved mouse to ({x},{y})")


def _gui_click(args: dict[str, Any]) -> ToolResult:
    pyautogui, err = _require_pyautogui()
    if pyautogui is None:
        return ToolResult(status="error", error=err)

    xy = _coerce_xy(args, pyautogui)
    if xy is None:
        w, h = _screen_size(pyautogui)
        return ToolResult(status="error", error=f"x/y inválidos (0<=x<{w}, 0<=y<{h})")

    x, y = xy
    pyautogui.click(x=x, y=y, button="left")
    return ToolResult(status="ok", output=f"clicked ({x},{y})")


def _gui_click_box_center(args: dict[str, Any]) -> ToolResult:
    pyautogui, err = _require_pyautogui()
    if pyautogui is None:
        return ToolResult(status="error", error=err)

    try:
        raw_x = args.get("x")
        raw_y = args.get("y")
        raw_w = args.get("w")
        raw_h = args.get("h")
        if raw_x is None or raw_y is None or raw_w is None or raw_h is None:
            return ToolResult(status="error", error="x/y/w/h ausentes")
        x = int(raw_x)
        y = int(raw_y)
        w = int(raw_w)
        h = int(raw_h)
    except Exception:
        return ToolResult(status="error", error="x/y/w/h inválidos")

    if w <= 0 or h <= 0:
        return ToolResult(status="error", error="w/h devem ser > 0")

    cx = x + (w // 2)
    cy = y + (h // 2)

    screen_w, screen_h = _screen_size(pyautogui)
    if cx < 0 or cy < 0 or cx >= screen_w or cy >= screen_h:
        return ToolResult(status="error", error=f"centro fora da tela (0<=x<{screen_w}, 0<=y<{screen_h})")

    pyautogui.click(x=cx, y=cy, button="left")
    return ToolResult(status="ok", output=f"clicked box center ({cx},{cy})")


def _gui_type_text(args: dict[str, Any]) -> ToolResult:
    pyautogui, err = _require_pyautogui()
    if pyautogui is None:
        return ToolResult(status="error", error=err)

    text = str(args.get("text", ""))
    if not text:
        return ToolResult(status="error", error="text vazio")

    # `write` simula digitação humana (menos suspeito em alguns contextos)
    pyautogui.write(text, interval=0.01)
    return ToolResult(status="ok", output=f"typed {len(text)} chars")
