"""Configuração de logging.

Rationale:
- Agentes autônomos precisam de logs para depuração e auditoria.
- Mantemos logs legíveis para humanos, sem imprimir segredos.
"""

from __future__ import annotations

import logging

from omniscia.core.config import Settings


def configure_logging(settings: Settings) -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Silencia bibliotecas barulhentas por padrão.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    # LiteLLM pode ser bem barulhento em INFO; default é WARNING.
    logging.getLogger("litellm").setLevel(logging.INFO if level <= logging.DEBUG else logging.WARNING)
