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
from omniscia.core.types import Plan

logger = logging.getLogger(__name__)


def run_brain_loop(settings: Settings) -> None:
    """Loop REPL do agente."""

    console = Console()
    registry = build_default_registry(settings=settings)

    console.print(Panel.fit("Omnisciência (MVP) — digite seu comando (ou 'sair')", title="OK"))

    while True:
        try:
            user_message = console.input("\nVocê> ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nEncerrando.")
            return

        if not user_message:
            continue

        plan = route(settings, user_message)

        if plan.intent == "exit":
            console.print(plan.final_response or "Encerrando.")
            return

        _execute_plan(console, settings, registry, plan)


def _execute_plan(console: Console, settings: Settings, registry, plan: Plan) -> None:
    console.print(Panel.fit(f"Intent: {plan.intent}\nRisk: {plan.risk}", title="Plano"))

    if not require_approval(plan, enabled=settings.hitl_enabled):
        console.print("Agente> Ok, não vou executar isso.")
        return

    # Execução sequencial simples.
    for call in plan.tool_calls:
        result = registry.run(call.tool_name, call.args)
        if result.status == "error":
            console.print(f"[red]Tool error:[/red] {call.tool_name}: {result.error}")
            console.print("Agente> Tive um erro executando o plano.")
            return

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
    else:
        console.print("Agente> Feito.")
