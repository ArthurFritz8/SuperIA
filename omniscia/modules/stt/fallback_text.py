"""STT por texto (fallback).

Rationale:
- É o modo mais estável para o MVP: funciona em qualquer máquina/CI.
- Também serve como fallback seguro quando microfone/dependências falharem.
"""

from __future__ import annotations

from rich.console import Console

from omniscia.modules.stt.base import SttProvider


class TextStt(SttProvider):
    def __init__(self, console: Console) -> None:
        self._console = console

    def listen(self) -> str:
        return self._console.input("\nVocê> ").strip()
