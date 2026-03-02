from __future__ import annotations

from omniscia.modules.tts.base import TtsProvider


class Pyttsx3Tts(TtsProvider):
    def __init__(self) -> None:
        import pyttsx3  # type: ignore[import-not-found]

        self._engine = pyttsx3.init()

    @property
    def enabled(self) -> bool:
        return True

    def speak(self, text: str) -> None:
        t = (text or "").strip()
        if not t:
            return
        self._engine.say(t)
        self._engine.runAndWait()
