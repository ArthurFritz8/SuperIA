from __future__ import annotations

from rich.console import Console

from omniscia.core.config import Settings
from omniscia.modules.stt.fallback_text import TextStt
from omniscia.modules.stt.factory import build_stt


def test_stt_vosk_without_model_dir_falls_back_to_text(monkeypatch):
    monkeypatch.setenv("OMNI_STT_MODE", "vosk")
    # Settings.load() carrega também do .env; então forçamos vazio para garantir fallback.
    monkeypatch.setenv("OMNI_STT_VOSK_MODEL_DIR", "")

    settings = Settings.load()
    console = Console(record=True)

    stt = build_stt(settings, console=console)

    assert isinstance(stt, TextStt)
    out = console.export_text()
    assert "OMNI_STT_VOSK_MODEL_DIR" in out
