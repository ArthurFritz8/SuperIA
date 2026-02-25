"""Esqueleto do loop de auto-correção (futuro).

O objetivo final do DevAgent é:
1) Entender um objetivo de engenharia ("crie um projeto X")
2) Gerar/alterar arquivos
3) Rodar comandos/tests
4) Se falhar, ler logs e iterar

Neste marco, implementamos a fundação: execução segura e ferramentas.
O loop de auto-correção com LLM entra quando habilitarmos um router/planner via LLM.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AutoFixConfig:
    max_iters: int = 5


class AutoCoder:
    def __init__(self, *, config: AutoFixConfig) -> None:
        self._cfg = config

    def run(self, goal: str) -> str:
        # Placeholder: será implementado quando conectarmos um planner LLM.
        return (
            "AutoCoder ainda não implementado. "
            "Use as tools dev.exec/dev.run_python para executar e depurar por enquanto."
        )
