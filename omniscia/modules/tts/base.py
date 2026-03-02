from __future__ import annotations

from abc import ABC, abstractmethod


class TtsProvider(ABC):
    @property
    def enabled(self) -> bool:  # pragma: no cover
        return False

    @abstractmethod
    def speak(self, text: str) -> None:
        raise NotImplementedError
