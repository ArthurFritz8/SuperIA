"""Tools custom (opt-in).

Para habilitar o carregamento automático, defina:
- OMNI_CUSTOM_TOOLS_ENABLED=true

Crie arquivos .py neste diretório com uma função:
- register(registry: ToolRegistry) -> None

A função será chamada durante o build do registry.
"""
