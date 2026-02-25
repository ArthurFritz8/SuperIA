"""Módulo DevAgent ("Programador Interno").

Objetivo:
- Permitir que o agente execute código e comande o ambiente de forma controlada.

Estratégia incremental:
1) Sandbox de execução de comandos (sem shell), com allowlist, timeout e truncamento.
2) Ferramentas (tools) do core: dev.exec, dev.run_python
3) (Depois) Loop de auto-correção: gerar patch, rodar, ler erro, iterar.

Nota de segurança:
- Executar comandos é uma capacidade perigosa.
- Por padrão, limitamos o que pode ser executado e mantemos HITL para ações críticas.
"""
