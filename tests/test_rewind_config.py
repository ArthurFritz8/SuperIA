from __future__ import annotations

from omniscia.core.config import Settings


def test_rewind_enabled_env_flag(monkeypatch):
    monkeypatch.setenv("OMNI_REWIND_ENABLED", "true")
    settings = Settings.load()
    assert settings.rewind_enabled is True


def test_rewind_clamps(monkeypatch):
    monkeypatch.setenv("OMNI_REWIND_ENABLED", "true")
    monkeypatch.setenv("OMNI_REWIND_SECONDS", "1")
    monkeypatch.setenv("OMNI_REWIND_INTERVAL_S", "0.01")
    settings = Settings.load()
    assert settings.rewind_seconds >= 30
    assert settings.rewind_interval_s >= 1.0

    monkeypatch.setenv("OMNI_REWIND_SECONDS", "9999")
    monkeypatch.setenv("OMNI_REWIND_INTERVAL_S", "999")
    settings2 = Settings.load()
    assert settings2.rewind_seconds <= 180
    assert settings2.rewind_interval_s <= 10.0
