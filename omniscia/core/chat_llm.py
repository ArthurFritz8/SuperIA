"""Chat (resposta em linguagem natural) via LiteLLM.

Rationale:
- O router LLM deve focar em gerar *planos* (tools + risco).
- Para perguntas que não exigem tools (ex.: orientação em jogos, dúvidas),
  queremos uma resposta conversacional direta e útil.

Política:
- Esta camada NÃO executa tools.
- Não deve afirmar que "viu a tela" sem screenshot/OCR explícito.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from typing import Any

from omniscia.core.config import Settings
from omniscia.core.litellm_env import apply_litellm_env, provider_requires_api_key
from omniscia.core.ollama_health import maybe_warn_if_ollama_cpu
from omniscia.core.redact import redact_secrets

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    try:
        v = int(str(os.getenv(name, str(default))).strip())
        return v if v > 0 else default
    except Exception:
        return default


def _should_use_smart_model(text: str) -> bool:
    """Heurística conservadora: usa modelo 'smart' só quando parece tarefa de código/debug.

    Motivo: modelos maiores (ex.: 8B) podem aumentar muito a latência.
    """

    t = (text or "").strip().lower()
    if "```" in t:
        return True
    if "traceback" in t or "stack trace" in t:
        return True
    if re.search(r"\b(keyerror|typeerror|valueerror|attributeerror|exception|segmentation fault)\b", t):
        return True
    if re.search(r"\b(debug|bug|erro|falha|crash|refator|otimiz|arquitet|projeto|c[oó]digo|algoritm)\b", t):
        return True
    return False


def _pick_chat_model(settings: Settings, user_text: str) -> str:
    """Seleciona o modelo para o chat.

    Defaults:
    - Usa `settings.llm_model`.
    - Se `OMNI_LLM_SMART_MODEL` estiver definido e o pedido parecer complexo, usa ele.
    """

    model = str(settings.llm_model or "").strip()
    smart = str(os.getenv("OMNI_LLM_SMART_MODEL", "") or "").strip()
    if smart and _should_use_smart_model(user_text):
        return smart
    return model


def warmup_llm_best_effort(settings: Settings, *, blocking: bool = False) -> None:
    """Faz warmup do modelo local para reduzir o cold-start (best-effort).

    Estratégia:
    - Dispara uma completion mínima com `max_tokens=1`.
    - Rodar em background para não travar o REPL.
    """

    try:
        provider = (getattr(settings, "llm_provider", None) or "").strip().lower()
        if provider != "ollama":
            return

        base_url = (getattr(settings, "llm_base_url", None) or "").strip() or None
        if not base_url:
            return

        model_main = str(getattr(settings, "llm_model", None) or "").strip()
        model_smart = str(os.getenv("OMNI_LLM_SMART_MODEL", "") or "").strip()
        model_router = str(os.getenv("OMNI_ROUTER_LLM_MODEL", "") or "").strip()

        warm_smart = (os.getenv("OMNI_LLM_WARMUP_SMART", "false").strip().lower() == "true")
        models = [m for m in [model_router, model_main] if m]
        if warm_smart and model_smart:
            models.append(model_smart)
        if not models:
            return

        apply_litellm_env(settings)
        from litellm import completion  # type: ignore

        max_tokens = 1
        base_kwargs: dict[str, Any] = {"api_base": base_url, "timeout": 12}
        msgs = [{"role": "user", "content": "warmup"}]

        def _run() -> None:
            for m in models:
                try:
                    completion(model=str(m), messages=msgs, temperature=0.0, max_tokens=max_tokens, **base_kwargs)
                except Exception as exc:  # noqa: BLE001
                    # warmup é best-effort
                    logger.debug("Warmup falhou para model=%s: %s", str(m), redact_secrets(str(exc)))

        if blocking:
            _run()
        else:
            threading.Thread(target=_run, daemon=True).start()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Warmup indisponível (best-effort): %s", redact_secrets(str(exc)))
        return


def _has_llm_config(settings: Settings) -> bool:
    needs_key = provider_requires_api_key(settings.llm_provider)
    has_key = bool((settings.llm_api_key or "").strip())
    return bool(settings.llm_provider and settings.llm_model and (has_key or not needs_key))


def _has_llm_config_values(provider: str | None, model: str | None, api_key: str | None) -> bool:
    needs_key = provider_requires_api_key(provider)
    has_key = bool((api_key or "").strip())
    return bool((provider or "").strip() and (model or "").strip() and (has_key or not needs_key))


def chat_reply(
    settings: Settings,
    user_message: str,
    *,
    history: list[dict[str, str]] | None = None,
    image_path: str | None = None,
    profile_context: str | None = None,
    temperature: float = 0.3,
    max_chars: int = 4000,
) -> str:
    """Gera uma resposta conversacional (sem tools).

    Args:
        history: lista opcional de mensagens no formato {role, content}.
                 Roles aceitas: "user" | "assistant".
    """

    if not _has_llm_config(settings):
        raise RuntimeError("LLM não configurado (OMNI_LLM_PROVIDER/OMNI_LLM_MODEL/OMNI_LLM_API_KEY)")

    model = _pick_chat_model(settings, str(user_message or ""))
    if not model:
        raise RuntimeError("LLM model não definido")

    apply_litellm_env(settings)

    try:
        from litellm import completion
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Dependência ausente: litellm") from exc

    system = (
        "Você é VOID, um assistente estilo Jarvis, útil, direto e humano no tom (sem fingir ser humano). "
        "Responda em PT-BR por padrão, a menos que o usuário peça outro idioma ou o PERFIL_DO_USUARIO indique outra preferência. "
        "Quando a pergunta for ambígua, faça 1-3 perguntas objetivas. "
        "Demonstre empatia e bom senso (ex.: reconhecer frustração), mas NÃO afirme ter sentimentos, consciência ou experiências pessoais. "
        "Não invente que viu a tela/janela; você só pode comentar sobre a tela se o usuário fornecer uma captura/OCR explicitamente. "
        "Se o usuário pedir apenas dicas/orientação (ex.: jogos), responda com passos práticos e opções, sem tools." 
    )

    msgs: list[dict[str, Any]] = [{"role": "system", "content": system}]

    # Perfil persistente (memória de longo prazo): usado para preferências de tom/idioma/estilo.
    # Inserimos como contexto do assistente para manter compatibilidade com providers.
    if profile_context and str(profile_context).strip():
        msgs.append({"role": "assistant", "content": str(profile_context).strip()[:1400]})

    if history:
        for m in history:
            role = (m.get("role") or "").strip().lower()
            content = str(m.get("content") or "")
            if role in {"user", "assistant"} and content.strip():
                msgs.append({"role": role, "content": content})

    # Optional: attach image for multimodal providers/models.
    # This is opt-in and may send screen content over the network.
    user_text = str(user_message or "").strip()
    if getattr(settings, "vlm_enabled", False) and image_path:
        try:
            from omniscia.core.vlm import image_file_to_data_url

            enc = image_file_to_data_url(image_path)
            msgs.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                user_text
                                + "\n\n[Contexto] O usuário anexou uma captura de tela (screenshot). "
                                + "Use a imagem para responder com precisão."
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": enc.data_url}},
                    ],
                }
            )
        except Exception as exc:  # noqa: BLE001
            logger.info("VLM indisponivel; seguindo sem imagem: %s", redact_secrets(str(exc)))
            msgs.append({"role": "user", "content": user_text})
    else:
        msgs.append({"role": "user", "content": user_text})

    max_tokens = _env_int("OMNI_CHAT_MAX_TOKENS", 256)
    timeout_s = float(os.getenv("OMNI_CHAT_TIMEOUT_S", "45").strip() or "45")

    def _call_llm(*, provider_settings: Settings, llm_model: str, llm_api_base: str | None) -> str:
        apply_litellm_env(provider_settings)
        # api_base é aceito pelo LiteLLM para vários providers (OpenAI-compat e Ollama).
        base_kwargs: dict[str, Any] = {}
        if llm_api_base:
            base_kwargs["api_base"] = llm_api_base
        base_kwargs["timeout"] = timeout_s

        try:
            resp: Any = completion(
                model=llm_model,
                messages=msgs,
                temperature=float(temperature),
                max_tokens=int(max_tokens),
                **base_kwargs,
            )
            maybe_warn_if_ollama_cpu(
                provider=getattr(provider_settings, "llm_provider", None),
                base_url=(getattr(provider_settings, "llm_base_url", None) or None),
                model=str(llm_model),
            )
            content: str = resp["choices"][0]["message"]["content"]  # type: ignore[index]
            return (content or "").strip()
        except Exception as exc:  # noqa: BLE001
            # Fallback: some providers/models reject multimodal payloads.
            # Retry once without image content.
            if any(isinstance(m.get("content"), list) for m in msgs if isinstance(m, dict)):
                logger.info(
                    "Falha no chat multimodal; retry sem imagem: %s",
                    redact_secrets(str(exc)),
                )
                msgs2: list[dict[str, Any]] = []
                for m in msgs:
                    if m.get("role") == "user" and isinstance(m.get("content"), list):
                        msgs2.append({"role": "user", "content": user_text})
                    else:
                        msgs2.append(m)
                resp2: Any = completion(
                    model=llm_model,
                    messages=msgs2,
                    temperature=float(temperature),
                    max_tokens=int(max_tokens),
                    **base_kwargs,
                )
                maybe_warn_if_ollama_cpu(
                    provider=getattr(provider_settings, "llm_provider", None),
                    base_url=(getattr(provider_settings, "llm_base_url", None) or None),
                    model=str(llm_model),
                )
                content2: str = resp2["choices"][0]["message"]["content"]  # type: ignore[index]
                return (content2 or "").strip()
            raise

    text = ""
    try:
        text = _call_llm(
            provider_settings=settings,
            llm_model=model,
            llm_api_base=(getattr(settings, "llm_base_url", None) or None),
        )
    except Exception as exc:  # noqa: BLE001
        # Automatic fallback if configured.
        fb_provider = getattr(settings, "llm_fallback_provider", None)
        fb_model = getattr(settings, "llm_fallback_model", None)
        fb_key = getattr(settings, "llm_fallback_api_key", None)
        fb_base = getattr(settings, "llm_fallback_base_url", None)

        if _has_llm_config_values(fb_provider, fb_model, fb_key):
            logger.warning(
                "Falha no chat LLM principal; tentando fallback (%s)",
                redact_secrets(str(exc)),
            )
            fb_settings = Settings(
                **{
                    **settings.__dict__,
                    "llm_provider": fb_provider,
                    "llm_model": fb_model,
                    "llm_api_key": fb_key,
                    "llm_base_url": fb_base,
                }
            )
            try:
                text = _call_llm(provider_settings=fb_settings, llm_model=str(fb_model), llm_api_base=fb_base)
            except Exception as exc2:  # noqa: BLE001
                logger.error("Falha no chat LLM (principal+fallback): %s", redact_secrets(str(exc2)))
                raise
        else:
            logger.error("Falha no chat LLM: %s", redact_secrets(str(exc)))
            raise

    if not text:
        return "Não consegui gerar uma resposta agora. Tente reformular sua pergunta."

    if len(text) > int(max_chars):
        text = text[: int(max_chars)] + "..."

    return text
