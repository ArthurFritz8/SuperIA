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

from omniscia.core.types import RiskLevel


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

    # STT (Whisper API) — opcional
    stt_openai_api_key: str | None = None
    stt_openai_model: str = "whisper-1"
    stt_record_seconds: float = 6.0
    stt_sample_rate: int = 16000

    # Segurança
    hitl_enabled: bool = True
    hitl_min_risk: RiskLevel = RiskLevel.CRITICAL
    hitl_require_token: bool = False

    # Web (Playwright)
    web_headless: bool = True

    # OCR (Tesseract)
    # No Windows, às vezes o tesseract.exe não está no PATH.
    tesseract_cmd: str | None = None

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
        hitl_require_token = (
            os.getenv("OMNI_HITL_REQUIRE_TOKEN", "false").strip().lower() == "true"
        )

        hitl_min_risk_raw = (os.getenv("OMNI_HITL_MIN_RISK", "CRITICAL") or "CRITICAL").strip().upper()
        try:
            hitl_min_risk = RiskLevel(hitl_min_risk_raw)
        except Exception:
            hitl_min_risk = RiskLevel.CRITICAL

        web_headless = (os.getenv("OMNI_WEB_HEADLESS", "true").strip().lower() != "false")

        tesseract_cmd = os.getenv("OMNI_TESSERACT_CMD") or None

        llm_provider = os.getenv("OMNI_LLM_PROVIDER") or None
        llm_model = os.getenv("OMNI_LLM_MODEL") or None
        llm_api_key = os.getenv("OMNI_LLM_API_KEY") or None

        stt_openai_api_key = os.getenv("OMNI_STT_OPENAI_API_KEY") or None
        stt_openai_model = os.getenv("OMNI_STT_OPENAI_MODEL", "whisper-1").strip() or "whisper-1"

        def _float_env(name: str, default: float) -> float:
            raw = (os.getenv(name) or "").strip()
            if not raw:
                return default
            try:
                return float(raw)
            except ValueError:
                return default

        def _int_env(name: str, default: int) -> int:
            raw = (os.getenv(name) or "").strip()
            if not raw:
                return default
            try:
                return int(raw)
            except ValueError:
                return default

        stt_record_seconds = _float_env("OMNI_STT_RECORD_SECONDS", 6.0)
        stt_sample_rate = _int_env("OMNI_STT_SAMPLE_RATE", 16000)

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

            stt_openai_api_key=stt_openai_api_key,
            stt_openai_model=stt_openai_model,
            stt_record_seconds=stt_record_seconds,
            stt_sample_rate=stt_sample_rate,
            hitl_enabled=hitl_enabled,
            hitl_min_risk=hitl_min_risk,
            hitl_require_token=hitl_require_token,
            web_headless=web_headless,
            tesseract_cmd=tesseract_cmd,
            log_level=log_level,
        )
