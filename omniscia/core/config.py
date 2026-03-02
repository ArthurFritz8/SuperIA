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
SttMode = Literal["text", "whisper_openai", "vosk"]
TtsMode = Literal["none", "pyttsx3"]
WakeWordMode = Literal["prefix", "anywhere", "smart"]


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

    # STT (Vosk offline) — opcional/grátis
    # Requer baixar um modelo e apontar a pasta.
    stt_vosk_model_dir: str | None = None

    # Áudio
    # Dispositivo de entrada (microfone) por índice do sounddevice.
    # Se None, usa o default do sistema.
    audio_input_device: int | None = None
    # Ganho do microfone aplicado no capture (útil quando o device vem muito baixo).
    audio_input_gain: float = 1.0

    # Wake word (voz)
    # Quando ligado e STT estiver em modo voz, o agente só responde após ouvir o wake word.
    wake_word_enabled: bool = False
    wake_word: str = "void"
    # prefix: "void ...", "ei void ..." (mais conservador)
    # anywhere: atende se "void" aparecer em qualquer parte da frase
    # smart: como anywhere, mas tenta evitar falsos positivos quando o usuário estiver falando de código
    wake_word_mode: WakeWordMode = "prefix"
    # Se true, ao ouvir apenas o wake word (sem comando) responde com um ack (ex: "Sim?").
    wake_word_ack: bool = True
    wake_word_ack_text: str = "Sim?"

    # Segurança
    hitl_enabled: bool = True
    hitl_min_risk: RiskLevel = RiskLevel.HIGH
    hitl_require_token: bool = False

    # Web (Playwright)
    web_headless: bool = True
    web_assume_https: bool = False

    # OCR (Tesseract)
    # No Windows, às vezes o tesseract.exe não está no PATH.
    tesseract_cmd: str | None = None

    # OS openers
    # Allowlist extra (JSON mapping app->target) para `os.open_app`.
    # - target pode ser: "calc.exe", "C:/Caminho/App.exe", ou "discord://".
    open_apps_file: str | None = None
    open_apps_json: str | None = None

    # Logs
    log_level: str = "INFO"

    # Omega (confiabilidade)
    # - Mantém defaults conservadores; ativar via OMNI_OMEGA=true.
    omega_enabled: bool = False
    retry_max_attempts: int = 1
    retry_backoff_s: float = 0.35
    retry_side_effect_tools: bool = False

    # Extensibilidade / Jarvis definitivo (opt-in)
    # Tools custom carregadas dinamicamente de omniscia/tools/custom
    custom_tools_enabled: bool = False
    # Permite que o agente escreva scripts temporários em scratch/ e rode via dev.run_python.
    # ATENÇÃO: isso habilita auto-código; mantenha HITL com token.
    self_coding_enabled: bool = False
    # Memória vetorial (ChromaDB) para RAG
    vector_memory_enabled: bool = False
    vector_memory_auto_index: bool = False
    # Hotkey global (Ctrl+Space) para capturar contexto de tela (screenshot + OCR)
    hotkey_screen_enabled: bool = False
    # Proatividade (scheduler): o agente pode alertar sobre CPU/RAM/processos
    proactive_enabled: bool = False
    proactive_interval_s: int = 300
    proactive_cpu_threshold: int = 95
    proactive_ram_threshold: int = 95

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

        hitl_min_risk_env = os.getenv("OMNI_HITL_MIN_RISK")
        if hitl_min_risk_env is None or not hitl_min_risk_env.strip():
            # Default seguro: exigir aprovação a partir de HIGH.
            hitl_min_risk_raw = "HIGH"
        else:
            hitl_min_risk_raw = hitl_min_risk_env.strip().upper()
        try:
            hitl_min_risk = RiskLevel(hitl_min_risk_raw)
        except Exception:
            hitl_min_risk = RiskLevel.HIGH

        web_headless = (os.getenv("OMNI_WEB_HEADLESS", "true").strip().lower() != "false")
        web_assume_https = (
            os.getenv("OMNI_WEB_ASSUME_HTTPS", "false").strip().lower() == "true"
        )

        tesseract_cmd = os.getenv("OMNI_TESSERACT_CMD") or None

        open_apps_file = os.getenv("OMNI_OPEN_APPS_FILE") or None
        open_apps_json = os.getenv("OMNI_OPEN_APPS_JSON") or None

        llm_provider = os.getenv("OMNI_LLM_PROVIDER") or None
        llm_model = os.getenv("OMNI_LLM_MODEL") or None
        llm_api_key = os.getenv("OMNI_LLM_API_KEY") or None

        stt_openai_api_key = os.getenv("OMNI_STT_OPENAI_API_KEY") or None
        stt_openai_model = os.getenv("OMNI_STT_OPENAI_MODEL", "whisper-1").strip() or "whisper-1"

        stt_vosk_model_dir = os.getenv("OMNI_STT_VOSK_MODEL_DIR") or None

        audio_input_device_raw = (os.getenv("OMNI_AUDIO_INPUT_DEVICE") or "").strip()
        if not audio_input_device_raw:
            audio_input_device = None
        else:
            try:
                audio_input_device = int(audio_input_device_raw)
            except ValueError:
                audio_input_device = None

        audio_input_gain_raw = (os.getenv("OMNI_AUDIO_INPUT_GAIN") or "").strip()
        if not audio_input_gain_raw:
            audio_input_gain = 1.0
        else:
            try:
                audio_input_gain = float(audio_input_gain_raw)
            except ValueError:
                audio_input_gain = 1.0

        if audio_input_gain < 0.1:
            audio_input_gain = 0.1
        if audio_input_gain > 50.0:
            audio_input_gain = 50.0

        def _bool_env(name: str, default: bool) -> bool:
            raw = (os.getenv(name) or "").strip().lower()
            if not raw:
                return default
            if raw in {"1", "true", "t", "yes", "y", "on"}:
                return True
            if raw in {"0", "false", "f", "no", "n", "off"}:
                return False
            return default

        wake_word_enabled = _bool_env("OMNI_WAKE_WORD_ENABLED", False)
        wake_word = (os.getenv("OMNI_WAKE_WORD", "void") or "void").strip() or "void"
        wake_word_mode_raw = (os.getenv("OMNI_WAKE_WORD_MODE", "prefix") or "prefix").strip().lower()
        wake_word_mode: WakeWordMode = "prefix"
        if wake_word_mode_raw in {"prefix", "anywhere", "smart"}:
            wake_word_mode = wake_word_mode_raw  # type: ignore[assignment]
        wake_word_ack = _bool_env("OMNI_WAKE_WORD_ACK", True)
        wake_word_ack_text = (os.getenv("OMNI_WAKE_WORD_ACK_TEXT", "Sim?") or "Sim?").strip() or "Sim?"

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

        omega_enabled = (os.getenv("OMNI_OMEGA", "false").strip().lower() == "true")
        retry_max_attempts = _int_env("OMNI_RETRY_MAX", 3 if omega_enabled else 1)
        retry_backoff_s = _float_env("OMNI_RETRY_BACKOFF_S", 0.35)
        retry_side_effect_tools = (
            os.getenv("OMNI_RETRY_SIDE_EFFECTS", "false").strip().lower() == "true"
        )

        custom_tools_enabled = _bool_env("OMNI_CUSTOM_TOOLS_ENABLED", False)
        self_coding_enabled = _bool_env("OMNI_SELF_CODING_ENABLED", False)
        vector_memory_enabled = _bool_env("OMNI_VECTOR_MEMORY_ENABLED", False)
        vector_memory_auto_index = _bool_env("OMNI_VECTOR_MEMORY_AUTO_INDEX", False)
        hotkey_screen_enabled = _bool_env("OMNI_HOTKEY_SCREEN_ENABLED", False)
        proactive_enabled = _bool_env("OMNI_PROACTIVE_ENABLED", False)
        proactive_interval_s = _int_env("OMNI_PROACTIVE_INTERVAL_S", 300)
        proactive_cpu_threshold = _int_env("OMNI_PROACTIVE_CPU_THRESHOLD", 95)
        proactive_ram_threshold = _int_env("OMNI_PROACTIVE_RAM_THRESHOLD", 95)

        if proactive_interval_s < 30:
            proactive_interval_s = 30
        if proactive_interval_s > 3600:
            proactive_interval_s = 3600
        if proactive_cpu_threshold < 1:
            proactive_cpu_threshold = 1
        if proactive_cpu_threshold > 100:
            proactive_cpu_threshold = 100
        if proactive_ram_threshold < 1:
            proactive_ram_threshold = 1
        if proactive_ram_threshold > 100:
            proactive_ram_threshold = 100

        # Clamp básico para evitar valores absurdos.
        if retry_max_attempts < 1:
            retry_max_attempts = 1
        if retry_max_attempts > 8:
            retry_max_attempts = 8
        if retry_backoff_s < 0.0:
            retry_backoff_s = 0.0
        if retry_backoff_s > 5.0:
            retry_backoff_s = 5.0

        # Normalização mínima: evita valores inválidos explodirem silenciosamente.
        if router_mode not in ("heuristic", "llm"):
            router_mode = "heuristic"
        if stt_mode not in ("text", "whisper_openai", "vosk"):
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
            stt_vosk_model_dir=stt_vosk_model_dir,
            audio_input_device=audio_input_device,
            audio_input_gain=audio_input_gain,
            wake_word_enabled=wake_word_enabled,
            wake_word=wake_word,
            wake_word_mode=wake_word_mode,
            wake_word_ack=wake_word_ack,
            wake_word_ack_text=wake_word_ack_text,
            hitl_enabled=hitl_enabled,
            hitl_min_risk=hitl_min_risk,
            hitl_require_token=hitl_require_token,
            web_headless=web_headless,
            web_assume_https=web_assume_https,
            tesseract_cmd=tesseract_cmd,
            open_apps_file=open_apps_file,
            open_apps_json=open_apps_json,
            log_level=log_level,
            omega_enabled=omega_enabled,
            retry_max_attempts=retry_max_attempts,
            retry_backoff_s=retry_backoff_s,
            retry_side_effect_tools=retry_side_effect_tools,

            custom_tools_enabled=custom_tools_enabled,
            self_coding_enabled=self_coding_enabled,
            vector_memory_enabled=vector_memory_enabled,
            vector_memory_auto_index=vector_memory_auto_index,
            hotkey_screen_enabled=hotkey_screen_enabled,
            proactive_enabled=proactive_enabled,
            proactive_interval_s=proactive_interval_s,
            proactive_cpu_threshold=proactive_cpu_threshold,
            proactive_ram_threshold=proactive_ram_threshold,
        )
