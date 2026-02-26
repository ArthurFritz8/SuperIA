"""Entrada CLI do Omnisciência.

Rationale:
- Usamos Typer para uma CLI simples e extensível.
- O comando default inicia o loop do cérebro.

Execute:
- `python -m omniscia.app`
- ou, se instalado como script: `omniscia`
"""

from __future__ import annotations

import typer

from omniscia.core.brain import run_brain_loop
from omniscia.core.config import Settings
from omniscia.core.logging import configure_logging

from omniscia.core.selftest import run_selftest

app = typer.Typer(add_completion=False, help="Omnisciência — assistente autônomo modular")


@app.callback(invoke_without_command=True)
def _default(ctx: typer.Context) -> None:
    """Comportamento default.

    Rationale:
    - Queremos que `python -m omniscia.app` já inicie o assistente (MVP simples).
    - Ao mesmo tempo, queremos um CLI extensível com subcomandos (ex: `memory`, `web`).

    Implementação:
    - Se nenhum subcomando for chamado, executamos `run()`.
    """

    if ctx.invoked_subcommand is None:
        run()


@app.command()
def run() -> None:
    """Inicia o loop principal do assistente."""

    settings = Settings.load()
    configure_logging(settings)
    run_brain_loop(settings)


@app.command()
def selftest() -> None:
    """Roda um conjunto curto de testes offline (sem gastar LLM).

    Útil para validar instalação, tools básicas e roteamento determinístico.
    """

    ok, report = run_selftest()
    typer.echo(report)
    if not ok:
        raise typer.Exit(code=1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
