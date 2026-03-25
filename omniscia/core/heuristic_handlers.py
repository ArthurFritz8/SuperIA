"""Heuristic routing handlers (Chain of Responsibility).

Objetivo:
- Tirar regras do "god function" `_route_heuristic` em `router.py`.
- Facilitar manutenção/adição de intenções sem depender da ordem de `if` gigantes.

Estratégia:
- Handlers pequenos, testáveis e independentes.
- Migração incremental: `router._route_heuristic()` chama `run_heuristic_handlers()`
  antes do bloco legado; regras novas/extraídas vivem aqui.

Nota:
- Este módulo NÃO importa `omniscia.core.router` para evitar ciclos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from omniscia.core.types import Plan, RiskLevel, ToolCall


class HeuristicHandler(Protocol):
    def try_handle(
        self,
        *,
        user_message: str,
        norm: str,
        context_messages: list[dict[str, str]] | None,
    ) -> Plan | None: ...


_RE_NUMERIC_ONLY = re.compile(r"^\d{1,3}$")

# Session toggles
_RE_OMEGA_WORD = re.compile(r"\b(omega|jarvis)\b")
_RE_TOGGLE_ON = re.compile(r"\b(ativar|ativa|liga|ligar|on|habilitar)\b")
_RE_TOGGLE_OFF = re.compile(r"\b(desativar|desativa|desliga|desligar|off)\b")

_RE_VOICE_OFF = re.compile(r"\b(silenciar|mute|sem\s+voz|tirar\s+voz|desativar\s+voz|desliga\s+a\s+voz)\b")
_RE_VOICE_ON = re.compile(r"\b(ativar\s+voz|liga\s+a\s+voz|ligar\s+voz|falar\s+resposta|fala\s+as\s+respostas)\b")

_RE_AUTONOMY_WORD = re.compile(r"\b(autonomia|autonomo|autopilot|piloto\s+automatico)\b")

# Profile updates
_RE_NAME_INTRO = re.compile(r"\b(meu\s+nome\s+e|meu\s+nome\s+é|pode\s+me\s+chamar\s+de|me\s+chame\s+de)\b")
_RE_LANG_EN = re.compile(r"\b(responda\s+em|fale\s+em)\s+(ingles|english)\b")
_RE_LANG_PT = re.compile(r"\b(responda\s+em|fale\s+em)\s+(portugues|português|pt\-br|brasil)\b")
_RE_VERB_SHORT = re.compile(r"\b(respostas\s+curtas|seja\s+curto|mais\s+curto|curtinho|objetivo)\b")
_RE_VERB_DETAILED = re.compile(r"\b(mais\s+detalhado|bem\s+detalhado|detalhe|com\s+detalhes|explica\s+melhor)\b")

# Crypto / knowledge
_RE_KNOW_WHAT_IS = re.compile(r"\b(conhece|conhecer|o\s+que\s+e|oque\s+e|o\s+que\s+é|me\s+fale\s+sobre|fala\s+sobre|explique)\b")
_RE_PI_NETWORK = re.compile(r"\bpi\s*network\b", flags=re.IGNORECASE)

_RE_CHART_WORD = re.compile(r"\b(grafico|gr[aá]fico|chart)\b")
_RE_ANALYZE_WORD = re.compile(r"\b(estude|estudar|analise|analisa|analisar|verifique|veja|mostre|estuda)\b")


def _guess_name_from_text(text: str) -> str | None:
    q = re.search(r"['\"]([^'\"]{2,60})['\"]", text)
    if q:
        return q.group(1).strip()
    m = re.search(r"\b(chamado|chamada|nome)\b\s+([\w\- ]{2,60})", text, flags=re.IGNORECASE)
    if m:
        return (m.group(2) or "").strip()
    return None


def _infer_subject_from_context(ctx: list[dict[str, str]] | None) -> str | None:
    if not ctx:
        return None

    for m in reversed(ctx[-12:]):
        text = str(m.get("content") or "").strip()
        if not text:
            continue

        if _RE_PI_NETWORK.search(text):
            return "Pi Network"

        for coin in ("Bitcoin", "Ethereum", "Solana", "Dogecoin", "Cardano", "XRP", "BNB"):
            if re.search(rf"\b{re.escape(coin)}\b", text, flags=re.IGNORECASE):
                return coin

        mm = re.search(
            r"\b(?:moeda|coin|cripto(?:moeda)?)\b\s+([A-Za-z0-9][A-Za-z0-9\-\._ ]{1,40})",
            text,
            flags=re.IGNORECASE,
        )
        if mm:
            cand = (mm.group(1) or "").strip(" .,:;!?\"'")
            if 2 <= len(cand) <= 40:
                return cand

    return None


@dataclass(frozen=True)
class NumericOnlyHandler:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        if not _RE_NUMERIC_ONLY.fullmatch(norm or ""):
            return None
        msg = user_message.strip()
        return Plan(
            intent="chat",
            user_message=msg,
            tool_calls=[],
            risk=RiskLevel.LOW,
            final_response=(
                "Eu não uso números como seleção de menu. "
                "Se você quer que eu execute a automação, repita o pedido completo (ex.: 'faça as atividades do PDF no Word'), "
                "ou diga explicitamente: 'pode executar agora' depois de colocar o PDF em foco."
            ),
        )


@dataclass(frozen=True)
class SessionTogglesHandler:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        msg = user_message.strip()

        if _RE_OMEGA_WORD.search(norm) and _RE_TOGGLE_ON.search(norm):
            return Plan(
                intent="core.omega_on",
                user_message=msg,
                tool_calls=[],
                risk=RiskLevel.LOW,
                final_response="Ok — modo omega ativado nesta sessão.",
            )

        if _RE_OMEGA_WORD.search(norm) and _RE_TOGGLE_OFF.search(norm):
            return Plan(
                intent="core.omega_off",
                user_message=msg,
                tool_calls=[],
                risk=RiskLevel.LOW,
                final_response="Ok — modo omega desativado nesta sessão.",
            )

        if _RE_VOICE_OFF.search(norm):
            return Plan(
                intent="core.voice_off",
                user_message=msg,
                tool_calls=[],
                risk=RiskLevel.LOW,
                final_response="Ok — voz desativada (modo silencioso).",
            )

        if _RE_VOICE_ON.search(norm):
            return Plan(
                intent="core.voice_on",
                user_message=msg,
                tool_calls=[],
                risk=RiskLevel.LOW,
                final_response="Ok — voz ativada para respostas (se disponível).",
            )

        if _RE_AUTONOMY_WORD.search(norm) and _RE_TOGGLE_ON.search(norm):
            return Plan(
                intent="core.autonomy_on",
                user_message=msg,
                tool_calls=[],
                risk=RiskLevel.LOW,
                final_response="Ok — autonomia ativada nesta sessão (tarefas mais longas).",
            )

        if _RE_AUTONOMY_WORD.search(norm) and _RE_TOGGLE_OFF.search(norm):
            return Plan(
                intent="core.autonomy_off",
                user_message=msg,
                tool_calls=[],
                risk=RiskLevel.LOW,
                final_response="Ok — autonomia desativada nesta sessão.",
            )

        return None


@dataclass(frozen=True)
class ProfilePrefsHandler:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        msg = user_message.strip()

        if _RE_NAME_INTRO.search(norm):
            nm = _guess_name_from_text(msg)
            if nm:
                return Plan(
                    intent="memory.profile_update",
                    user_message=msg,
                    tool_calls=[ToolCall(tool_name="memory.profile_update", args={"patch": {"name": nm}})],
                    risk=RiskLevel.LOW,
                    final_response=f"Ok — vou te chamar de {nm}.",
                )

        if _RE_LANG_EN.search(norm):
            return Plan(
                intent="memory.profile_update",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="memory.profile_update", args={"patch": {"language": "en"}})],
                risk=RiskLevel.LOW,
                final_response="Ok — vou responder em inglês.",
            )

        if _RE_LANG_PT.search(norm):
            return Plan(
                intent="memory.profile_update",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="memory.profile_update", args={"patch": {"language": "pt-BR"}})],
                risk=RiskLevel.LOW,
                final_response="Ok — vou responder em PT-BR.",
            )

        if _RE_VERB_SHORT.search(norm):
            return Plan(
                intent="memory.profile_update",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="memory.profile_update", args={"patch": {"verbosity": "short"}})],
                risk=RiskLevel.LOW,
                final_response="Ok — vou ser mais curto e objetivo.",
            )

        if _RE_VERB_DETAILED.search(norm):
            return Plan(
                intent="memory.profile_update",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="memory.profile_update", args={"patch": {"verbosity": "detailed"}})],
                risk=RiskLevel.LOW,
                final_response="Ok — vou responder com mais detalhes.",
            )

        return None


@dataclass(frozen=True)
class CryptoKnowledgeHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        msg = user_message.strip()

        if _RE_KNOW_WHAT_IS.search(norm) and _RE_PI_NETWORK.search(norm):
            return Plan(
                intent="knowledge.wikipedia_summary",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="knowledge.wikipedia_summary", args={"query": "Pi Network", "lang": "pt"})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar um resumo confiável (Wikipedia).",
            )

        if _RE_CHART_WORD.search(norm) and _RE_ANALYZE_WORD.search(norm):
            asset: str | None = None
            if _RE_PI_NETWORK.search(norm):
                asset = "pi network"
            if asset is None:
                asset = _infer_subject_from_context(context_messages)
            if asset is not None:
                return Plan(
                    intent="finance.crypto_market_chart",
                    user_message=msg,
                    tool_calls=[ToolCall(tool_name="finance.crypto_market_chart", args={"asset": asset, "vs": "usd", "days": "30"})],
                    risk=RiskLevel.MEDIUM,
                    final_response="Ok — vou puxar dados históricos (CoinGecko) e resumir o gráfico.",
                )

        return None


_HANDLERS: tuple[HeuristicHandler, ...] = (
    NumericOnlyHandler(),
    SessionTogglesHandler(),
    ProfilePrefsHandler(),
    CryptoKnowledgeHandlers(),
)


def run_heuristic_handlers(
    *,
    user_message: str,
    norm: str,
    context_messages: list[dict[str, str]] | None,
) -> Plan | None:
    for h in _HANDLERS:
        try:
            plan = h.try_handle(user_message=user_message, norm=norm, context_messages=context_messages)
        except Exception:
            # Heurística nunca deve derrubar o router; fallback para o legado.
            continue
        if plan is not None:
            return plan
    return None
