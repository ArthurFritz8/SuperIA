"""ToolRunner: validação e execução centralizada de tools.

Objetivo:
- Validar argumentos produzidos por LLM contra schemas Pydantic por tool.
- Evitar quebra em runtime por tipos/chaves alucinadas.
- Padronizar erros para que o loop ReAct possa pedir correção sem crash.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, ValidationError

from omniscia.core.tools import ToolRegistry
from omniscia.core.types import ToolResult

logger = logging.getLogger(__name__)


class ToolArgsBase(BaseModel):
    """Base de args para tools.

    - `extra='forbid'` impede chaves alucinadas.
    - Models concretos devem herdar e declarar campos.
    """

    model_config = {
        "extra": "forbid",
    }


def _validation_error_to_message(tool_name: str, err: ValidationError) -> str:
    details = err.errors(include_url=False)
    return json.dumps(
        {
            "tool": tool_name,
            "error": "invalid_args",
            "details": details,
        },
        ensure_ascii=False,
    )


class ToolRunner:
    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry
        self._schemas: dict[str, type[ToolArgsBase]] = {}

    def register_schema(self, tool_name: str, schema: type[ToolArgsBase]) -> None:
        self._schemas[(tool_name or "").strip()] = schema

    def _coerce_args(self, args: dict[str, Any] | None) -> dict[str, Any]:
        return dict(args or {})

    def validate_args(self, tool_name: str, args: dict[str, Any] | None) -> dict[str, Any] | None:
        name = (tool_name or "").strip()
        schema = self._schemas.get(name)
        if schema is None:
            return self._coerce_args(args)
        try:
            model = schema.model_validate(self._coerce_args(args))
            return model.model_dump(mode="python")
        except ValidationError as exc:
            logger.warning("Args inválidos para tool %s", name)
            return None

    def run(self, tool_name: str, args: dict[str, Any] | None) -> ToolResult:
        name = (tool_name or "").strip()
        schema = self._schemas.get(name)
        coerced = self._coerce_args(args)

        if schema is not None:
            try:
                model = schema.model_validate(coerced)
                coerced = model.model_dump(mode="python")
            except ValidationError as exc:
                return ToolResult(status="error", error=_validation_error_to_message(name, exc))

        return self._registry.run(name, coerced)

    async def run_async(self, tool_name: str, args: dict[str, Any] | None) -> ToolResult:
        name = (tool_name or "").strip()
        schema = self._schemas.get(name)
        coerced = self._coerce_args(args)

        if schema is not None:
            try:
                model = schema.model_validate(coerced)
                coerced = model.model_dump(mode="python")
            except ValidationError as exc:
                return ToolResult(status="error", error=_validation_error_to_message(name, exc))

        return await self._registry.run_async(name, coerced)
