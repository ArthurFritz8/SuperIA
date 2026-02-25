"""Fábrica de STT.

Rationale:
- O core pede um provider e não quer conhecer detalhes de implementação.
- Implementamos fallback automático para TextStt se Whisper não estiver configurado.

Política de fallback:
- Se `stt_mode=text`: sempre TextStt.
- Se `stt_mode=whisper_openai` mas faltar API key/deps: mostra aviso e cai para TextStt.
"""

from __future__ import annotations

import logging

from rich.console import Console

from omniscia.core.config import Settings
from omniscia.modules.stt.base import SttProvider
from omniscia.modules.stt.fallback_text import TextStt

logger = logging.getLogger(__name__)


def build_stt(settings: Settings, *, console: Console) -> SttProvider:
    if settings.stt_mode == "text":
        return TextStt(console)

    if settings.stt_mode == "whisper_openai":
        if not settings.stt_openai_api_key:
            console.print(
                "[yellow]STT Whisper selecionado, mas falta OMNI_STT_OPENAI_API_KEY. "
                "Caindo para modo texto.[/yellow]"
            )
            return TextStt(console)

        try:
            from omniscia.modules.stt.whisper_openai import WhisperConfig, WhisperOpenAIStt

            return WhisperOpenAIStt(
                config=WhisperConfig(
                    api_key=settings.stt_openai_api_key,
                    model=settings.stt_openai_model,
                    record_seconds=settings.stt_record_seconds,
                    sample_rate=settings.stt_sample_rate,
                )
            )
        except Exception:
            logger.exception("Falha ao inicializar Whisper STT; caindo para texto")
            console.print(
                "[yellow]Falha ao iniciar STT Whisper (deps/microfone). Caindo para modo texto.[/yellow]"
            )
            return TextStt(console)

    # Safety net
    return TextStt(console)
