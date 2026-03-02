"""Exemplo de tool custom (opt-in).

Este módulo é carregado automaticamente pelo loader quando:
- OMNI_CUSTOM_TOOLS_ENABLED=true

Ele registra uma tool simples `custom.ping` para validar que o plugin system está ok.
"""

from __future__ import annotations

from typing import Any

from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult


def _ping(args: dict[str, Any]) -> ToolResult:
    text = str(args.get("text", "")).strip()
    if text:
        return ToolResult(status="ok", output=f"pong: {text}")
    return ToolResult(status="ok", output="pong")


def register(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="custom.ping",
            description="Tool de exemplo (custom) para validar o loader: retorna 'pong'",
            risk="LOW",
            fn=_ping,
        )
    )
