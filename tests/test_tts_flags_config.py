from __future__ import annotations

from omniscia.core.config import Settings


def test_tts_speak_flags_default_silent():
    settings = Settings.load()
    assert settings.tts_speak_responses is False
    assert settings.tts_speak_alerts is False
    assert settings.tts_speak_wake_ack is False


def test_tts_speak_flags_env(monkeypatch):
    monkeypatch.setenv("OMNI_TTS_SPEAK_RESPONSES", "true")
    monkeypatch.setenv("OMNI_TTS_SPEAK_ALERTS", "true")
    monkeypatch.setenv("OMNI_TTS_SPEAK_WAKE_ACK", "true")
    settings = Settings.load()
    assert settings.tts_speak_responses is True
    assert settings.tts_speak_alerts is True
    assert settings.tts_speak_wake_ack is True
