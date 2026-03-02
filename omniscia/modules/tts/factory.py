"""TTS factory.

Rationale:
- Mirrors the STT factory design.
- Keeps core decoupled from concrete TTS implementations.

Fallback policy:
- If tts_mode=none: always NoneTts
- If tts_mode=pyttsx3 but deps fail: warn and fallback to NoneTts
"""

from __future__ import annotations

import logging

from rich.console import Console

from omniscia.core.config import Settings
from omniscia.modules.tts.base import TtsProvider
from omniscia.modules.tts.fallback_none import NoneTts

logger = logging.getLogger(__name__)


def build_tts(settings: Settings, *, console: Console) -> TtsProvider:
    if settings.tts_mode == "none":
        return NoneTts()

    if settings.tts_mode == "pyttsx3":
        try:
            from omniscia.modules.tts.pyttsx3_tts import Pyttsx3Tts

            return Pyttsx3Tts()
        except Exception:
            logger.exception("Falha ao inicializar TTS pyttsx3; caindo para none")
            console.print("[yellow]Falha ao iniciar TTS (pyttsx3). Caindo para modo silencioso.[/yellow]")
            return NoneTts()

    return NoneTts()
