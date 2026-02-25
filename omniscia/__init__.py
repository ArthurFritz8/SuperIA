"""Omnisciência — pacote principal.

Este projeto é modular por design: o núcleo ("cérebro") não depende diretamente

- de microfone/alto-falante (voz),
- de automação de GUI (mouse/teclado),
- de browser automation,
- nem de bancos vetoriais.

Isso permite evoluir o assistente por camadas, mantendo um MVP funcional e testável.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
