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

app = typer.Typer(add_completion=False, help="Omnisciência — assistente autônomo modular")


@app.command()
def run() -> None:
    """Inicia o loop principal do assistente."""

    settings = Settings.load()
    configure_logging(settings)
    run_brain_loop(settings)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
