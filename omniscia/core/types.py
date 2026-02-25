"""Tipos e schemas do Core.

Rationale:
- Em agentes autônomos, a disciplina de schemas evita que o LLM "invente" campos.
- Pydantic nos dá validação e (futuramente) serialização estável para logs/memória.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ToolCall(BaseModel):
    """Uma chamada de ferramenta.

    `args` é propositalmente um dict genérico: cada tool valida seus próprios inputs.
    """

    tool_name: str
    args: dict[str, Any] = Field(default_factory=dict)


class Plan(BaseModel):
    """Plano de ação do agente.

    `intent` ajuda no roteamento humano/observabilidade.
    `tool_calls` é a lista ordenada do que executar.

    `risk` é avaliado pelo router e pode disparar HITL.
    """

    intent: str
    user_message: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    risk: RiskLevel = RiskLevel.LOW

    # Resposta final a ser dita/mostrada ao usuário após execução.
    final_response: str | None = None


class ToolResult(BaseModel):
    status: Literal["ok", "error", "skipped"]
    output: str | None = None
    error: str | None = None
