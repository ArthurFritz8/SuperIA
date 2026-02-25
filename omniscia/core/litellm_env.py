"""Configuração de ambiente para LiteLLM.

Motivação:
- O LiteLLM usa variáveis de ambiente específicas por provider (ex: GEMINI_API_KEY).
- Nosso projeto usa OMNI_LLM_* como interface única.

Este módulo faz o mapeamento sem logar segredos.
"""

from __future__ import annotations

from omniscia.core.config import Settings


def apply_litellm_env(settings: Settings) -> None:
    """Aplica variáveis de ambiente esperadas pelo LiteLLM.

    Observação:
    - Não valida a chave (isso é responsabilidade da chamada HTTP).
    - Não registra/loga segredos.
    """

    import os

    provider = (settings.llm_provider or "").strip()
    api_key = (settings.llm_api_key or "").strip()

    if provider:
        os.environ["LITELLM_PROVIDER"] = provider
    if api_key:
        os.environ["LITELLM_API_KEY"] = api_key

    p = provider.lower().strip().rstrip("/")

    # Google AI Studio (Gemini)
    if p in {"gemini", "google_ai_studio", "google-ai-studio", "google"} and api_key:
        os.environ["GEMINI_API_KEY"] = api_key

    # OpenAI compat (se você usar)
    if p in {"openai"} and api_key:
        os.environ["OPENAI_API_KEY"] = api_key

    # Anthropic (se você usar)
    if p in {"anthropic"} and api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key
