"""Router (interpretação de comandos -> plano).

Rationale:
- Um agente sério separa *entendimento* (router) de *execução* (tools).
- Assim podemos trocar a fonte de inteligência: heurística, LLM, regras, etc.

Este MVP tem dois modos:
- heuristic: regras simples e previsíveis
- llm: usa LiteLLM (multi-provider). Se faltar config, cai para heuristic.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from omniscia.core.config import Settings
from omniscia.core.types import Plan, RiskLevel, ToolCall

logger = logging.getLogger(__name__)


def route(settings: Settings, user_message: str) -> Plan:
    if settings.router_mode == "llm":
        plan = _route_with_llm(settings, user_message)
        if plan is not None:
            return plan

    return _route_heuristic(user_message)


def _route_heuristic(user_message: str) -> Plan:
    msg = user_message.strip()
    lower = msg.lower()

    # Regra: memória
    if re.search(r"\b(lembra|lembrar|memória|memoria|o que falamos|histórico|historico)\b", lower):
        # Extrai query simples removendo palavras comuns.
        q = re.sub(r"\b(lembra|lembrar|memória|memoria|o que falamos|histórico|historico)\b", "", lower)
        q = q.strip() or msg
        return Plan(
            intent="memory.search",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="memory.search", args={"query": q, "limit": 5})],
            risk=RiskLevel.LOW,
            final_response="Busquei na memória recente.",
        )

    # Regra: web read-only (ler página)
    # Se detectar uma URL ou intenção clara de abrir/ler um site.
    m = re.search(r"https?://\S+", msg)
    if m or re.search(r"\b(abra|abrir|ler|leia|resuma|resumir)\b.*\b(site|página|pagina)\b", lower):
        url = m.group(0) if m else ""
        return Plan(
            intent="web.read",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="web.get_page_text", args={"url": url, "max_chars": 6000})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok, vou abrir a página e extrair o texto (read-only).",
        )

    # Regra 0: saída
    if lower in {"sair", "exit", "quit"}:
        return Plan(intent="exit", user_message=msg, final_response="Encerrando.")

    # Regra 1: operações potencialmente críticas
    # Ex: "apague", "delete", "rm -rf" etc.
    if re.search(r"\b(apagar|delete|deletar|rm\s+-rf|formatar)\b", lower):
        return Plan(
            intent="filesystem.delete",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="echo", args={"text": "(stub) delete"})],
            risk=RiskLevel.CRITICAL,
            final_response="Ação de apagar detectada. Preciso de confirmação (HITL).",
        )

    # Regra 2: escrever arquivo
    if lower.startswith("crie um arquivo") or lower.startswith("criar arquivo"):
        # Exemplo esperado: "crie um arquivo path=foo.txt conteúdo=..."
        return Plan(
            intent="dev.write_file",
            user_message=msg,
            tool_calls=[
                ToolCall(
                    tool_name="write_file",
                    args={
                        "path": "notes.txt",
                        "content": f"Comando: {msg}\n",
                    },
                )
            ],
            risk=RiskLevel.HIGH,
            final_response="Ok, vou criar um arquivo (relativo ao workspace).",
        )

    # Default: ecoa e responde
    return Plan(
        intent="chat",
        user_message=msg,
        tool_calls=[ToolCall(tool_name="echo", args={"text": msg})],
        risk=RiskLevel.LOW,
        final_response="Entendi. (MVP: roteador heurístico)",
    )


def _route_with_llm(settings: Settings, user_message: str) -> Plan | None:
    """Usa LLM para produzir um Plan em JSON.

    Rationale:
    - Mantemos o LLM como "gerador de estrutura" (JSON), não como executor.
    - Validamos via Pydantic antes de aceitar.

    Segurança:
    - Se config estiver ausente, retornamos None e caímos no heurístico.
    """

    if not (settings.llm_provider and settings.llm_model and settings.llm_api_key):
        logger.warning("Router LLM habilitado, mas falta OMNI_LLM_*; caindo no heurístico")
        return None

    try:
        from litellm import completion
    except Exception:  # noqa: BLE001
        logger.exception("litellm não disponível; caindo no heurístico")
        return None

    system = (
        "Você é um roteador de ferramentas para um agente autônomo. "
        "Gere APENAS JSON válido no seguinte formato:\n"
        "{\n"
        "  \"intent\": string,\n"
        "  \"user_message\": string,\n"
        "  \"risk\": \"LOW\"|\"MEDIUM\"|\"HIGH\"|\"CRITICAL\",\n"
        "  \"tool_calls\": [ { \"tool_name\": string, \"args\": object } ],\n"
        "  \"final_response\": string\n"
        "}\n"
        "Ferramentas disponíveis (nomes): echo, write_file. "
        "Se o usuário pedir para apagar arquivos, comprar, logar, pagar, transferir dinheiro: use risk=CRITICAL."
    )

    # Não logamos a key; só configuramos no ambiente do litellm.
    import os

    os.environ["LITELLM_PROVIDER"] = settings.llm_provider
    os.environ["LITELLM_API_KEY"] = settings.llm_api_key

    try:
        resp = completion(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
        )

        content: str = resp["choices"][0]["message"]["content"]  # type: ignore[index]
        data: dict[str, Any] = json.loads(content)
        return Plan.model_validate(data)
    except Exception:  # noqa: BLE001
        logger.exception("Falha ao rotear via LLM; caindo no heurístico")
        return None
