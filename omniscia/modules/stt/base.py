"""Interfaces de Speech-to-Text (STT).

Rationale:
- STT é um detalhe de I/O. O core só quer "me dê uma string de comando".
- Uma interface simples permite alternar entre:
  - texto (terminal)
  - Whisper API
  - modelos offline

Importante:
- Este STT não faz *decisão* nem *ação*; apenas captura o que o usuário disse.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class SttProvider(ABC):
  @property
  def is_voice(self) -> bool:
    """Indica se este provider captura áudio de voz.

    Rationale:
    - O loop do cérebro pode ajustar UX (ex: mostrar "gravando...").
    - Também evita mensagens erradas quando há fallback para texto.
    """

    return False

    @abstractmethod
    def listen(self) -> str:
        """Bloqueia até obter um comando do usuário (string)."""

        raise NotImplementedError
