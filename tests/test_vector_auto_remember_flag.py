from __future__ import annotations

from omniscia.core.config import Settings


def test_vector_memory_auto_remember_flag(monkeypatch):
    monkeypatch.setenv("OMNI_VECTOR_MEMORY_AUTO_REMEMBER", "true")
    settings = Settings.load()
    assert settings.vector_memory_auto_remember is True
