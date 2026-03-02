"""STT via Whisper API (OpenAI) com captura de microfone.

Rationale:
- Whisper API dá boa qualidade sem precisar de GPU.
- Captura simples "push-to-talk" (grava N segundos) reduz complexidade inicial.

Dependências opcionais:
- `sounddevice` para capturar áudio do microfone
- `soundfile` para serializar WAV

Segurança/privacidade:
- O áudio é enviado para a API; use conscientemente.
- Não logamos o conteúdo do áudio nem a API key.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import httpx

from omniscia.modules.stt.base import SttProvider


@dataclass(frozen=True)
class WhisperConfig:
    api_key: str
    model: str = "whisper-1"
    record_seconds: float = 6.0
    sample_rate: int = 16000
    input_device: int | None = None


class WhisperOpenAIStt(SttProvider):
    def __init__(self, *, config: WhisperConfig) -> None:
        self._cfg = config

    @property
    def is_voice(self) -> bool:
        return True

    def listen(self) -> str:
        """Grava por alguns segundos e transcreve."""

        audio_wav = _record_wav_bytes(
            record_seconds=self._cfg.record_seconds,
            sample_rate=self._cfg.sample_rate,
            input_device=self._cfg.input_device,
        )
        return _whisper_transcribe(
            api_key=self._cfg.api_key,
            model=self._cfg.model,
            wav_bytes=audio_wav,
        )


def _record_wav_bytes(*, record_seconds: float, sample_rate: int, input_device: int | None) -> bytes:
    """Captura áudio do microfone e retorna WAV em memória.

    Implementação:
    - Captura mono float32 via sounddevice.
    - Converte para WAV PCM via soundfile.

    Por quê mono/16k?
    - Whisper funciona bem com 16kHz, e mono reduz payload.
    """

    try:
        import sounddevice as sd  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Dependência ausente: sounddevice. Instale com `pip install sounddevice soundfile`."
        ) from exc

    try:
        import soundfile as sf  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Dependência ausente: soundfile. Instale com `pip install sounddevice soundfile`."
        ) from exc

    frames = int(max(0.5, record_seconds) * sample_rate)

    # Gravação bloqueante: simples e previsível para o MVP.
    data = sd.rec(
        frames,
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        device=input_device,
    )
    sd.wait()

    buf = io.BytesIO()
    sf.write(buf, data, sample_rate, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def _whisper_transcribe(*, api_key: str, model: str, wav_bytes: bytes) -> str:
    """Chama a API de transcrição do OpenAI."""

    url = "https://api.openai.com/v1/audio/transcriptions"

    # Multipart/form-data: arquivo + campos.
    files = {
        "file": ("audio.wav", wav_bytes, "audio/wav"),
    }
    data = {
        "model": model,
        # Pode ser ajustado depois: prompt/language/temperature.
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, headers=headers, data=data, files=files)
    except httpx.RequestError as exc:
        raise RuntimeError(f"Whisper API network error: {exc}") from exc

    if resp.status_code >= 400:
        # Evita cuspir payload gigante no terminal (custo/tokens).
        body = (resp.text or "").strip()
        if len(body) > 800:
            body = body[:800] + "... [truncado]"
        raise RuntimeError(f"Whisper API error {resp.status_code}: {body}")

    payload = resp.json()
    text = str(payload.get("text", "")).strip()
    return text
