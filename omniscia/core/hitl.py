"""Human-in-the-Loop (HITL).

Rationale:
- Autonomia sem guardrails vira "acidente".
- Definimos um gate simples e auditável: ações CRITICAL exigem aprovação explícita.

Importante:
- HITL deve ser aplicado antes do side-effect.
- O texto de confirmação deve ser claro (o que vai acontecer, por quê, impacto).
"""

from __future__ import annotations

import json
import secrets
import sys
from typing import Any

from omniscia.core.types import Plan, RiskLevel


def require_approval(
    plan: Plan,
    *,
    enabled: bool,
    min_risk: RiskLevel = RiskLevel.CRITICAL,
    require_token: bool = False,
) -> bool:
    """Retorna True se aprovado, False se negado.

    Estratégia:
    - `RiskLevel.CRITICAL` sempre pede confirmação (se HITL habilitado).
    - Para outros níveis, por enquanto não bloqueia (pode evoluir para políticas).

    Implementação:
    - Usamos stdin/stdout para funcionar em qualquer ambiente.
    - Aceita apenas "YES" (case-insensitive) para evitar confirmações acidentais.
    """

    if not enabled:
        return True

    if _risk_rank(plan.risk) < _risk_rank(min_risk):
        return True

    token = secrets.token_hex(2).upper() if require_token else None

    print("\n[HITL] APROVAÇÃO NECESSÁRIA")
    print(f"Intent: {plan.intent}")
    print(f"Risk: {plan.risk} (min_risk={min_risk})")
    print("Motivo: risk >= min_risk")
    print(f"Plano: {len(plan.tool_calls)} chamada(s) de ferramenta")
    for i, call in enumerate(plan.tool_calls, start=1):
        safe_args = _redact_args(call.args)
        args_str = json.dumps(safe_args, ensure_ascii=False)
        if len(args_str) > 300:
            args_str = args_str[:300] + "... [truncado]"
        print(f"  {i}. {call.tool_name} args={args_str}")

    if require_token:
        assert token is not None
        print(f"\nDigite: YES {token} para autorizar. Qualquer outra coisa cancela.")
    else:
        print("\nDigite YES para autorizar. Qualquer outra coisa cancela.")
    sys.stdout.write("> ")
    sys.stdout.flush()
    answer = sys.stdin.readline().strip()

    if not answer:
        print("[HITL] Sem confirmação. Ação cancelada.")
        return False

    normalized = " ".join(answer.strip().split())
    up = normalized.upper()
    if require_token:
        assert token is not None
        if up == f"YES {token}":
            return True
    else:
        if up == "YES":
            return True

    print("[HITL] Negado pelo usuário. Ação cancelada.")
    return False


def _risk_rank(risk: RiskLevel) -> int:
    order = {
        RiskLevel.LOW: 0,
        RiskLevel.MEDIUM: 1,
        RiskLevel.HIGH: 2,
        RiskLevel.CRITICAL: 3,
    }
    return order.get(risk, 3)


def _redact_args(args: dict[str, Any]) -> dict[str, Any]:
    """Redige campos sensíveis e trunca strings longas para exibição no HITL."""

    def redact_value(k: str, v: Any) -> Any:
        key = (k or "").lower()
        if any(s in key for s in ["key", "token", "password", "secret"]):
            return "***"
        if isinstance(v, str) and len(v) > 200:
            return v[:200] + "... [truncado]"
        return v

    safe: dict[str, Any] = {}
    for k, v in (args or {}).items():
        try:
            safe[k] = redact_value(str(k), v)
        except Exception:
            safe[str(k)] = "[unprintable]"
    return safe
