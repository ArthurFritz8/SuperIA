"""Configuração do Omnisciência via variáveis de ambiente.

Rationale:
- Segredos (API keys) *não* podem ficar hard-coded.
- `.env` é conveniente em dev, mas deve ser ignorado pelo Git.

Este módulo mantém o core desacoplado de qualquer provedor específico.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from dotenv import load_dotenv


RouterMode = Literal["heuristic", "llm"]
SttMode = Literal["text", "whisper_openai"]
TtsMode = Literal["none", "pyttsx3"]


@dataclass(frozen=True)
class Settings:
    # Router
    router_mode: RouterMode = "heuristic"

    # LLM (opcional)
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None

    # I/O
    stt_mode: SttMode = "text"
    tts_mode: TtsMode = "none"

    # Segurança
    hitl_enabled: bool = True

    # Web (Playwright)
    web_headless: bool = True

    # Logs
    log_level: str = "INFO"

    @staticmethod
    def load() -> "Settings":
        """Carrega settings do ambiente.

        - Chamamos `load_dotenv()` para suportar `.env` local.
        - Mantemos defaults seguros (HITL ligado, router heurístico).
        """

        load_dotenv(override=False)

        import os

        router_mode = os.getenv("OMNI_ROUTER_MODE", "heuristic").strip() or "heuristic"
        stt_mode = os.getenv("OMNI_STT_MODE", "text").strip() or "text"
        tts_mode = os.getenv("OMNI_TTS_MODE", "none").strip() or "none"
        hitl_enabled = (os.getenv("OMNI_HITL_ENABLED", "true").strip().lower() != "false")

        web_headless = (os.getenv("OMNI_WEB_HEADLESS", "true").strip().lower() != "false")

        llm_provider = os.getenv("OMNI_LLM_PROVIDER") or None
        llm_model = os.getenv("OMNI_LLM_MODEL") or None
        llm_api_key = os.getenv("OMNI_LLM_API_KEY") or None

        log_level = os.getenv("OMNI_LOG_LEVEL", "INFO").strip() or "INFO"

        # Normalização mínima: evita valores inválidos explodirem silenciosamente.
        if router_mode not in ("heuristic", "llm"):
            router_mode = "heuristic"
        if stt_mode not in ("text", "whisper_openai"):
            stt_mode = "text"
        if tts_mode not in ("none", "pyttsx3"):
            tts_mode = "none"

        return Settings(
            router_mode=router_mode,  # type: ignore[arg-type]
            llm_provider=llm_provider,
            llm_model=llm_model,
            llm_api_key=llm_api_key,
            stt_mode=stt_mode,  # type: ignore[arg-type]
            tts_mode=tts_mode,  # type: ignore[arg-type]
            hitl_enabled=hitl_enabled,
            web_headless=web_headless,
            log_level=log_level,
        )
