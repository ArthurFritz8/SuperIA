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
from typing import Any

from omniscia.core.config import Settings
from omniscia.core.litellm_env import apply_litellm_env, provider_requires_api_key
from omniscia.core.redact import redact_secrets

logger = logging.getLogger(__name__)


def _has_llm_config(settings: Settings) -> bool:
    needs_key = provider_requires_api_key(settings.llm_provider)
    has_key = bool((settings.llm_api_key or "").strip())
    return bool(settings.llm_provider and settings.llm_model and (has_key or not needs_key))


def chat_reply(
    settings: Settings,
    user_message: str,
    *,
    history: list[dict[str, str]] | None = None,
    image_path: str | None = None,
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

    apply_litellm_env(settings)

    try:
        from litellm import completion
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Dependência ausente: litellm") from exc

    system = (
        "Você é VOID, um assistente estilo Jarvis, útil e direto. "
        "Responda em PT-BR. "
        "Quando a pergunta for ambígua, faça 1-3 perguntas objetivas. "
        "Não invente que viu a tela/janela; você só pode comentar sobre a tela se o usuário fornecer uma captura/OCR explicitamente. "
        "Se o usuário pedir apenas dicas/orientação (ex.: jogos), responda com passos práticos e opções, sem tools." 
    )

    msgs: list[dict[str, Any]] = [{"role": "system", "content": system}]

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

    try:
        try:
            resp: Any = completion(
                model=settings.llm_model,
                messages=msgs,
                temperature=float(temperature),
            )
            content: str = resp["choices"][0]["message"]["content"]  # type: ignore[index]
            text = (content or "").strip()
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
                resp = completion(model=settings.llm_model, messages=msgs2, temperature=float(temperature))
                content = resp["choices"][0]["message"]["content"]  # type: ignore[index]
                text = (content or "").strip()
            else:
                raise
    except Exception as exc:  # noqa: BLE001
        logger.error("Falha no chat LLM: %s", redact_secrets(str(exc)))
        raise

    if not text:
        return "Não consegui gerar uma resposta agora. Tente reformular sua pergunta."

    if len(text) > int(max_chars):
        text = text[: int(max_chars)] + "..."

    return text
