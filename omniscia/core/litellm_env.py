"""Configuração de ambiente para LiteLLM.

Motivação:
- O LiteLLM usa variáveis de ambiente específicas por provider (ex: GEMINI_API_KEY).
- Nosso projeto usa OMNI_LLM_* como interface única.

Este módulo faz o mapeamento sem logar segredos.
"""

from __future__ import annotations

from omniscia.core.config import Settings


def provider_requires_api_key(provider: str | None) -> bool:
    """Return True if this provider should require an API key.

    Default is conservative (True) for unknown providers.
    """

    p = (provider or "").strip().lower().rstrip("/")
    if not p:
        return True

    # Local / no-auth providers
    if p in {"ollama"}:
        return False

    # Known cloud providers
    if p in {
        "gemini",
        "google_ai_studio",
        "google-ai-studio",
        "google",
        "openai",
        "anthropic",
        "groq",
    }:
        return True

    return True


def apply_litellm_env(settings: Settings) -> None:
    """Aplica variáveis de ambiente esperadas pelo LiteLLM.

    Observação:
    - Não valida a chave (isso é responsabilidade da chamada HTTP).
    - Não registra/loga segredos.
    """

    import os

    provider = (settings.llm_provider or "").strip()
    api_key = (settings.llm_api_key or "").strip()
    base_url = (getattr(settings, "llm_base_url", None) or "").strip()

    if provider:
        os.environ["LITELLM_PROVIDER"] = provider
    if api_key:
        os.environ["LITELLM_API_KEY"] = api_key
    if base_url:
        # LiteLLM reads this for some providers; we also pass api_base explicitly in calls.
        os.environ["LITELLM_API_BASE"] = base_url

    p = provider.lower().strip().rstrip("/")

    # Google AI Studio (Gemini)
    if p in {"gemini", "google_ai_studio", "google-ai-studio", "google"} and api_key:
        os.environ["GEMINI_API_KEY"] = api_key

    # OpenAI compat (se você usar)
    if p in {"openai"} and api_key:
        os.environ["OPENAI_API_KEY"] = api_key
        if base_url:
            os.environ["OPENAI_API_BASE"] = base_url

    # Anthropic (se você usar)
    if p in {"anthropic"} and api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key

    # Groq (se você usar)
    if p in {"groq"} and api_key:
        os.environ["GROQ_API_KEY"] = api_key

    # Ollama (local; sem key)
    if p in {"ollama"} and base_url:
        # Used by some LiteLLM paths and by OpenAI-compatible wrappers.
        os.environ["OLLAMA_API_BASE"] = base_url
