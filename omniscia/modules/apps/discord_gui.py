"""Automação simples do Discord via GUI.

Motivação:
- OCR + clique é frágil (muitos matches na UI).
- O Discord tem atalhos úteis (ex: Ctrl+K) que tornam o fluxo mais estável.

Limitações:
- Requer que a janela do Discord esteja em foco.
- Não usa API do Discord (sem tokens); é puro teclado.
"""

from __future__ import annotations

import time
from typing import Any

from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult
from omniscia.modules.os_control.win_windows import focus_window_by_title_contains


def register_discord_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="discord.send_message",
            description=(
                "Envia uma mensagem no Discord via GUI (Ctrl+K -> selecionar -> digitar -> Enter). "
                "Requer que o Discord esteja em foco."
            ),
            risk="CRITICAL",
            fn=_discord_send_message,
        )
    )


def _require_pyautogui():
    try:
        import pyautogui

        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.05
        return pyautogui, None
    except Exception as exc:  # noqa: BLE001
        return None, f"pyautogui indisponível: {exc}"


def _discord_send_message(args: dict[str, Any]) -> ToolResult:
    """Send a Discord message using keyboard shortcuts.

    Args:
    - to: nome/handle para buscar no switcher (obrigatório)
    - message: texto da mensagem (obrigatório)
    - settle_ms: tempo de espera antes de começar (default 600)
    """

    to = str(args.get("to", "") or "").strip()
    message = str(args.get("message", "") or "").strip()
    settle_ms = int(args.get("settle_ms", 900) or 900)
    retries = int(args.get("retries", 1) or 1)
    if retries < 0:
        retries = 0
    if retries > 2:
        retries = 2

    if not to:
        return ToolResult(status="error", error="to vazio")
    if not message:
        return ToolResult(status="error", error="message vazio")

    pyautogui, err = _require_pyautogui()
    if pyautogui is None:
        return ToolResult(status="error", error=err)

    def _attempt() -> None:
        # Pequena espera para dar tempo do app focar.
        time.sleep(max(0.0, float(settle_ms) / 1000.0))

        # Se estivermos no Windows, tentamos focar/restaurar a janela do Discord.
        # Isso permite funcionar mesmo minimizado ou em outro monitor.
        rect = focus_window_by_title_contains("discord", timeout_s=2.5)
        if rect:
            # Uma pequena margem para evitar clicar na borda.
            win_w = max(1, int(rect["right"] - rect["left"]))
            win_h = max(1, int(rect["bottom"] - rect["top"]))
            # Clique na região inferior do cliente (onde fica o input de chat).
            x_win = int(rect["left"] + (win_w * 0.50))
            y_win = int(rect["top"] + (win_h * 0.93))
        else:
            x_win = None
            y_win = None

        # Fecha overlays/modais que podem capturar teclado.
        pyautogui.press("esc")
        time.sleep(0.05)
        pyautogui.press("esc")
        time.sleep(0.08)

        # Ctrl+K abre o Quick Switcher.
        pyautogui.hotkey("ctrl", "k")
        time.sleep(0.25)

        # Digita o alvo e confirma.
        pyautogui.write(to, interval=0.01)
        time.sleep(0.25)
        pyautogui.press("enter")

        # Espera a conversa abrir e a UI estabilizar.
        time.sleep(0.7)

        # Garante foco na caixa de mensagem clicando na parte inferior central.
        if x_win is None or y_win is None:
            w, h = pyautogui.size()
            x_win = int(w * 0.50)
            y_win = int(h * 0.93)

        pyautogui.click(x=int(x_win), y=int(y_win), button="left")
        time.sleep(0.1)

        # Digita a mensagem e envia.
        pyautogui.write(message, interval=0.01)
        time.sleep(0.05)
        pyautogui.press("enter")

    try:
        for attempt_i in range(retries + 1):
            try:
                _attempt()
                break
            except Exception:
                if attempt_i >= retries:
                    raise
                time.sleep(0.35)

        return ToolResult(status="ok", output=f"sent message to '{to}' ({len(message)} chars)")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))
