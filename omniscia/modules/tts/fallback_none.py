from __future__ import annotations

from omniscia.modules.tts.base import TtsProvider


class NoneTts(TtsProvider):
    @property
    def enabled(self) -> bool:
        return False

    def speak(self, text: str) -> None:
        return
