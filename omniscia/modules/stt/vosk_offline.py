"""STT offline usando Vosk (grátis).

Requer:
- `vosk` instalado (pip)
- Um modelo baixado e descompactado em uma pasta local
  (ex: OMNI_STT_VOSK_MODEL_DIR=C:\\models\\vosk-pt)

Notas:
- Captura áudio via `sounddevice` (já usado no Whisper).
- Retorna texto simples (sem pontuação avançada).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import sounddevice as sd
import numpy as np

from omniscia.modules.stt.base import SttProvider


@dataclass(frozen=True)
class VoskConfig:
    model_dir: str
    record_seconds: float = 6.0
    sample_rate: int = 16000
    input_device: int | None = None
    input_gain: float = 1.0


class VoskOfflineStt(SttProvider):
    def __init__(self, *, config: VoskConfig) -> None:
        from vosk import Model  # type: ignore[import-not-found]

        model_path = Path(config.model_dir)
        if not model_path.is_dir():
            raise FileNotFoundError(f"Vosk model dir não existe: {model_path}")

        self._cfg = config
        self._model = Model(str(model_path))

    @property
    def is_voice(self) -> bool:
        return True

    def listen(self) -> str:
        seconds = max(0.5, float(self._cfg.record_seconds))
        model_sample_rate = int(self._cfg.sample_rate)

        # Muitos microfones/driver no Windows não capturam bem em 16000 Hz.
        # Capturamos no sample rate padrão do device e reamostramos para o
        # sample rate do modelo antes de enviar ao Vosk.
        try:
            dev_info = sd.query_devices(self._cfg.input_device, "input")
            capture_sample_rate = int(float(dev_info.get("default_samplerate") or model_sample_rate))
        except Exception:
            capture_sample_rate = model_sample_rate

        if capture_sample_rate <= 0:
            capture_sample_rate = model_sample_rate

        audio_f32 = sd.rec(
            int(seconds * capture_sample_rate),
            samplerate=capture_sample_rate,
            channels=1,
            dtype="float32",
            device=self._cfg.input_device,
        )
        sd.wait()

        x = audio_f32.reshape(-1).astype(np.float32, copy=False)

        # Remove DC offset (ajuda em alguns drivers/placas no Windows)
        if x.size:
            x = x - float(np.mean(x))

        gain = float(self._cfg.input_gain or 1.0)
        if gain != 1.0:
            x = x * gain

        # Resample (linear) se necessário.
        if capture_sample_rate != model_sample_rate and x.size > 1:
            new_len = int(round(x.size * (model_sample_rate / float(capture_sample_rate))))
            new_len = max(1, new_len)
            xp = np.arange(x.size, dtype=np.float32)
            x_new = np.linspace(0.0, float(x.size - 1), num=new_len, dtype=np.float32)
            x = np.interp(x_new, xp, x).astype(np.float32, copy=False)

        # Corte adaptativo de silêncio no começo/fim (VAD simples por energia).
        # Isso melhora muito quando há ruído constante ou quando o usuário só fala no meio.
        x = _trim_leading_trailing_silence(x, sample_rate=model_sample_rate)

        # Normalização leve (se estiver baixo, tenta trazer para um pico útil).
        x = _gentle_peak_normalize(x, target_peak=0.35, max_gain=6.0)

        # Clip seguro antes de converter.
        x = np.clip(x, -1.0, 1.0)
        audio_i16 = (x * 32767.0).astype(np.int16)

        data = audio_i16.tobytes()

        # Cria um recognizer novo por rodada para evitar “estado sujo” entre escutas.
        from vosk import KaldiRecognizer  # type: ignore[import-not-found]

        recognizer = KaldiRecognizer(self._model, int(model_sample_rate))

        # Em áudio contínuo, o Vosk pode finalizar um segmento no meio
        # (AcceptWaveform=True) e o FinalResult() acabar vazio. Por isso,
        # acumulamos textos de Result() e FinalResult().
        texts: list[str] = []
        chunk_size = 4000  # bytes (~0.125s @ 16kHz mono int16)
        for i in range(0, len(data), chunk_size):
            piece = data[i : i + chunk_size]
            if recognizer.AcceptWaveform(piece):
                try:
                    payload = json.loads(recognizer.Result())
                    t = (payload.get("text") or "").strip()
                    if t:
                        texts.append(t)
                except Exception:
                    pass

        try:
            payload_final = json.loads(recognizer.FinalResult())
            t_final = (payload_final.get("text") or "").strip()
            if t_final:
                texts.append(t_final)
        except Exception:
            pass

        return " ".join(texts).strip()


def _trim_leading_trailing_silence(x: np.ndarray, *, sample_rate: int) -> np.ndarray:
    if x.size < 10 or sample_rate <= 0:
        return x

    # Frame curto o suficiente pra “ver” fala, longo o suficiente pra ser estável.
    frame_ms = 20
    frame = int(max(1, round(sample_rate * (frame_ms / 1000.0))))
    hop = frame

    n_frames = int(x.size // hop)
    if n_frames < 5:
        return x

    # Energia por frame (mean square). Usa float64 para estabilidade numérica.
    energies = np.empty(n_frames, dtype=np.float64)
    for i in range(n_frames):
        seg = x[i * hop : i * hop + frame]
        energies[i] = float(np.mean(np.square(seg.astype(np.float64, copy=False))))

    # Estima “ruído de fundo” como percentil baixo (robusto a fala).
    noise_floor = float(np.percentile(energies, 20.0))
    # Threshold adaptativo; protege contra silêncio absoluto.
    thr = max(noise_floor * 3.0, 1e-7)

    active = energies > thr
    if not np.any(active):
        return x

    # Padding para não cortar consoantes.
    pad = 2
    first = int(np.argmax(active))
    last = int(len(active) - 1 - np.argmax(active[::-1]))
    first = max(0, first - pad)
    last = min(len(active) - 1, last + pad)

    start = first * hop
    end = min(x.size, (last + 1) * hop)

    # Evita retornar áudio pequeno demais (threshold pode falhar em voz muito baixa).
    if end - start < int(0.25 * sample_rate):
        return x

    return x[start:end]


def _gentle_peak_normalize(x: np.ndarray, *, target_peak: float, max_gain: float) -> np.ndarray:
    if x.size == 0:
        return x
    peak = float(np.max(np.abs(x)))
    if peak <= 1e-8:
        return x

    # Só amplifica se estiver realmente baixo.
    if peak >= target_peak:
        return x

    gain = min(float(max_gain), float(target_peak / peak))
    if gain <= 1.01:
        return x
    y = x * gain
    return np.clip(y, -1.0, 1.0)
