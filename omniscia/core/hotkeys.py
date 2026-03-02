"""Hotkeys globais (opt-in).

Atalho principal:
- Ctrl+Space: arma captura de contexto de tela (screenshot + OCR) para a próxima mensagem.

Segurança/UX:
- O atalho é considerado um pedido explícito de 'ver a tela'.
- Não executa automação destrutiva; apenas captura contexto.
"""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)


def start_screen_hotkey_listener(flag: threading.Event) -> None:
    """Inicia listener em thread; seta `flag` quando Ctrl+Space for pressionado."""

    try:
        from pynput.keyboard import GlobalHotKeys
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Dependência ausente: pynput") from exc

    def _arm() -> None:
        flag.set()

    # Mantemos a instância viva dentro da thread.
    def _run() -> None:
        try:
            with GlobalHotKeys({"<ctrl>+<space>": _arm}) as h:
                h.join()
        except Exception:
            logger.exception("Hotkey listener falhou")

    t = threading.Thread(target=_run, name="hotkeys", daemon=True)
    t.start()
