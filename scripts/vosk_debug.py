from __future__ import annotations

import json
import os
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd


def rms(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=np.float32).reshape(-1)
    return float(np.sqrt(np.mean(np.square(x))))


def write_wav_int16(path: Path, sample_rate: int, audio_i16: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_i16.tobytes())


def main() -> int:
    from omniscia.core.config import Settings

    settings = Settings.load()

    model_dir = settings.stt_vosk_model_dir or ""
    record_seconds = float(settings.stt_record_seconds)
    sample_rate = int(settings.stt_sample_rate)
    device = settings.audio_input_device
    gain = float(settings.audio_input_gain or 1.0)

    print("Settings:")
    print("  model_dir:", repr(model_dir))
    print("  record_seconds:", record_seconds)
    print("  sample_rate:", sample_rate)
    print("  input_device:", device)
    print("  input_gain:", gain)

    if not model_dir:
        print("ERROR: stt_vosk_model_dir is empty")
        return 2

    model_path = Path(model_dir)
    print("Resolved model_path:", model_path.resolve() if model_path.exists() else model_path)
    print("Model path exists:", model_path.is_dir())

    from vosk import KaldiRecognizer, Model  # type: ignore

    print("Loading Vosk model...")
    model = Model(str(model_path))
    rec = KaldiRecognizer(model, sample_rate)
    rec.SetWords(True)

    print(f"Recording ~{record_seconds:.1f}s... speak now")
    audio_f32 = sd.rec(
        int(record_seconds * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        device=device,
    )
    sd.wait()

    x = audio_f32.reshape(-1).astype(np.float32)
    print("Audio stats:")
    print("  rms:", rms(x))
    print("  maxabs:", float(np.max(np.abs(x))))

    if gain != 1.0:
        x = x * gain
        print("After gain:")
        print("  rms:", rms(x))
        print("  maxabs:", float(np.max(np.abs(x))))

    x = np.clip(x, -1.0, 1.0)
    audio_i16 = (x * 32767.0).astype(np.int16)

    out_wav = Path("data/tmp/vosk_debug.wav")
    write_wav_int16(out_wav, sample_rate, audio_i16)
    print("Wrote:", out_wav)

    data = audio_i16.tobytes()
    chunk = 4000  # bytes
    print("Feeding recognizer in chunks...")
    for i in range(0, len(data), chunk):
        piece = data[i : i + chunk]
        if rec.AcceptWaveform(piece):
            try:
                print("Result:", json.loads(rec.Result()))
            except Exception:
                print("Result(raw):", rec.Result())

    try:
        final = json.loads(rec.FinalResult())
    except Exception:
        final = {"raw": rec.FinalResult()}
    print("FinalResult:", final)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
