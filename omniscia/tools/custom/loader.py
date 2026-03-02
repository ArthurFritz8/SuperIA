"""Loader de tools custom (opt-in).

Segurança:
- Desligado por padrão.
- Tools custom rodam no mesmo processo do agente.
- Use com HITL forte e apenas em máquinas confiáveis.

Contrato:
- Cada módulo Python em `omniscia.tools.custom` pode expor `register(registry)`.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from types import ModuleType

from omniscia.core.tools import ToolRegistry

logger = logging.getLogger(__name__)


def load_custom_tools(registry: ToolRegistry) -> None:
    """Importa módulos em `omniscia.tools.custom` e registra tools via `register()`.

    Falha suave: um módulo quebrado não derruba o agente.
    """

    try:
        pkg = importlib.import_module("omniscia.tools.custom")
    except Exception:
        logger.exception("Falha importando pacote de tools custom")
        return

    assert isinstance(pkg, ModuleType)

    for mod in pkgutil.iter_modules(getattr(pkg, "__path__", [])):
        name = mod.name
        if name in {"loader"}:
            continue

        full = f"omniscia.tools.custom.{name}"
        try:
            m = importlib.import_module(full)
            fn = getattr(m, "register", None)
            if callable(fn):
                fn(registry)
                logger.info("Custom tools carregadas: %s", full)
            else:
                logger.info("Custom module sem register(): %s", full)
        except Exception:
            logger.exception("Falha carregando custom tool module: %s", full)
