from __future__ import annotations

from omniscia.core.config import Settings


def test_vlm_enabled_env_flag(monkeypatch):
    monkeypatch.setenv("OMNI_VLM_ENABLED", "true")
    settings = Settings.load()
    assert settings.vlm_enabled is True
