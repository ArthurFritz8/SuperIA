"""O Cérebro (loop principal).

Responsabilidades:
- Receber input (MVP: texto; depois voz)
- Rotejar para um plano (heurístico ou LLM)
- Aplicar políticas (HITL)
- Executar ferramentas e retornar uma resposta final

Observação importante:
- Neste estágio, a interação é via terminal para manter o MVP simples e robusto.
- A voz (STT/TTS) entra como módulos plugáveis posteriormente.
"""

from __future__ import annotations

import logging

from rich.console import Console
from rich.panel import Panel

from omniscia.core.config import Settings
from omniscia.core.hitl import require_approval
from omniscia.core.router import route
from omniscia.core.tools import build_default_registry
from omniscia.core.types import Plan, RiskLevel
from omniscia.modules.stt.factory import build_stt
from omniscia.modules.memory.store import JsonlMemoryStore

logger = logging.getLogger(__name__)


def run_brain_loop(settings: Settings) -> None:
    """Loop REPL do agente."""

    console = Console()
    memory = JsonlMemoryStore()
    registry = build_default_registry(settings=settings, memory_store=memory)
    stt = build_stt(settings, console=console)

    console.print(Panel.fit("Omnisciência (MVP) — digite seu comando (ou 'sair')", title="OK"))

    while True:
        try:
            if stt.is_voice:
                console.print(
                    f"\n[dim]Gravando por ~{settings.stt_record_seconds}s... fale agora.[/dim]"
                )
            user_message = stt.listen().strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nEncerrando.")
            return
        except Exception as exc:  # noqa: BLE001
            # Se o STT falhar (microfone, deps), caímos para texto no próximo loop.
            logger.exception("Falha no STT")
            console.print(f"[red]Erro no STT:[/red] {exc}")
            console.print("[yellow]Voltando para modo texto.[/yellow]")
            settings = Settings(
                **{**settings.__dict__, "stt_mode": "text"},  # type: ignore[arg-type]
            )
            stt = build_stt(settings, console=console)
            continue

        if not user_message:
            continue

        memory.append("user_message", {"text": user_message})

        plan = route(settings, user_message)

        memory.append(
            "plan",
            {
                "intent": plan.intent,
                "risk": str(plan.risk),
                "tool_calls": [c.model_dump() for c in plan.tool_calls],
            },
        )

        if plan.intent == "exit":
            console.print(plan.final_response or "Encerrando.")
            return

        _execute_plan(console, settings, registry, plan, memory)


def _execute_plan(console: Console, settings: Settings, registry, plan: Plan, memory: JsonlMemoryStore) -> None:
    effective_risk = _effective_risk_for_plan(plan, registry)
    effective_plan = plan if effective_risk == plan.risk else plan.model_copy(update={"risk": effective_risk})

    if effective_plan.risk != plan.risk:
        memory.append(
            "plan_effective_risk",
            {"intent": plan.intent, "router_risk": str(plan.risk), "effective_risk": str(effective_plan.risk)},
        )

    if effective_plan.risk == plan.risk:
        console.print(Panel.fit(f"Intent: {plan.intent}\nRisk: {plan.risk}", title="Plano"))
    else:
        console.print(
            Panel.fit(
                f"Intent: {plan.intent}\nRisk(router): {plan.risk}\nRisk(effective): {effective_plan.risk}",
                title="Plano",
            )
        )

    if not require_approval(
        effective_plan,
        enabled=settings.hitl_enabled,
        min_risk=settings.hitl_min_risk,
        require_token=settings.hitl_require_token,
    ):
        console.print("Agente> Ok, não vou executar isso.")
        return

    # Execução sequencial simples.
    for call in plan.tool_calls:
        result = registry.run(call.tool_name, call.args)
        if result.status == "error":
            console.print(f"[red]Tool error:[/red] {call.tool_name}: {result.error}")
            console.print("Agente> Tive um erro executando o plano.")
            return

        memory.append(
            "tool_output",
            {
                "tool": call.tool_name,
                "args": call.args,
                "status": result.status,
                "output": result.output,
                "error": result.error,
            },
        )

        # Observabilidade do MVP:
        # - Em agentes, tool output é parte essencial do feedback loop.
        # - Truncamos para não poluir o terminal nem expor dados demais por acidente.
        if result.status == "ok" and result.output:
            out = result.output.strip()
            if len(out) > 2000:
                out = out[:2000] + "\n... [truncado]"
            console.print(Panel(out, title=f"Tool: {call.tool_name}"))

    if plan.final_response:
        console.print(f"Agente> {plan.final_response}")
        memory.append("agent_response", {"text": plan.final_response})
    else:
        console.print("Agente> Feito.")
        memory.append("agent_response", {"text": "Feito."})


def _effective_risk_for_plan(plan: Plan, registry) -> RiskLevel:
    """Calcula o risco efetivo (router + risco intrínseco das tools).

    Motivação:
    - O router/LLM pode subestimar risco.
    - Tools têm um risco intrínseco declarado no registry.

    Política:
    - Risco efetivo = max(router_risk, max(tool_risk)).
    - Tool desconhecida => CRITICAL (fail closed).
    """

    def rank(r: RiskLevel) -> int:
        return {
            RiskLevel.LOW: 0,
            RiskLevel.MEDIUM: 1,
            RiskLevel.HIGH: 2,
            RiskLevel.CRITICAL: 3,
        }.get(r, 3)

    def parse_tool_risk(risk_str: str) -> RiskLevel:
        raw = (risk_str or "LOW").strip().upper()
        try:
            return RiskLevel(raw)
        except Exception:
            return RiskLevel.LOW

    current = plan.risk

    for call in plan.tool_calls:
        try:
            spec = registry.get(call.tool_name)
            tool_risk = parse_tool_risk(getattr(spec, "risk", "LOW"))
        except Exception:
            tool_risk = RiskLevel.CRITICAL

        if rank(tool_risk) > rank(current):
            current = tool_risk

    return current
