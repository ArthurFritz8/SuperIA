"""Human-in-the-Loop (HITL).

Rationale:
- Autonomia sem guardrails vira "acidente".
- Definimos um gate simples e auditável: ações CRITICAL exigem aprovação explícita.

Importante:
- HITL deve ser aplicado antes do side-effect.
- O texto de confirmação deve ser claro (o que vai acontecer, por quê, impacto).
"""

from __future__ import annotations

import sys

from omniscia.core.types import Plan, RiskLevel


def require_approval(plan: Plan, *, enabled: bool) -> bool:
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

    if plan.risk != RiskLevel.CRITICAL:
        return True

    print("\n[HITL] AÇÃO CRÍTICA DETECTADA")
    print(f"Intent: {plan.intent}")
    print(f"Plano: {len(plan.tool_calls)} chamada(s) de ferramenta")
    for i, call in enumerate(plan.tool_calls, start=1):
        print(f"  {i}. {call.tool_name} args={call.args}")

    print("\nDigite YES para autorizar. Qualquer outra coisa cancela.")
    sys.stdout.write("> ")
    sys.stdout.flush()
    answer = sys.stdin.readline().strip()

    if answer.upper() == "YES":
        return True

    print("[HITL] Negado pelo usuário. Ação cancelada.")
    return False
