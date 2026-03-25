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
import logging
from datetime import datetime
from dataclasses import dataclass
from typing import Protocol

from omniscia.core.types import Plan, RiskLevel, ToolCall


logger = logging.getLogger(__name__)


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

# Filesystem / VS Code
_RE_FS_WORD = re.compile(r"\b(arquivo|arquivos|pasta|pastas|diretorio|diret[óo]rio|folder|file|files|dir)\b")
_RE_LIST_WORD = re.compile(r"\b(listar|lista|mostre|mostrar|ver|veja|quais|conte[uú]do|conteudo)\b")
_RE_READ_WORD = re.compile(r"\b(ler|leia|abra|abrir|ver|mostrar|exibir|conte[uú]do|conteudo)\b")
_RE_VSCODE_WORD = re.compile(r"\b(vscode|vs\s*code|visual\s+studio\s+code)\b")
_RE_TASKS_WORD = re.compile(r"\b(tasks\.json|tasks|tarefas)\b")
_RE_SETTINGS_WORD = re.compile(r"\b(settings\.json|settings|configura[cç][aã]o|configura[cç][oõ]es)\b")
_RE_LAUNCH_WORD = re.compile(r"\b(launch\.json|launch|depurar|debug)\b")

# Screen / vision
_RE_SCREEN_WORD = re.compile(r"\b(tela|screen)\b")
_RE_REWIND_WORD = re.compile(r"\b(monitorar|monitoramento|monitoramento\s+cont[ií]nuo|rewind)\b")
_RE_STATUS_WORD = re.compile(r"\b(status|estado|como\s+esta|como\s+est[aá])\b")
_RE_STOP_WORD = re.compile(r"\b(parar|pare|desligar|desliga|stop|encerrar|encerre)\b")
_RE_START_WORD = re.compile(r"\b(come[cç]ar|comece|iniciar|inicie|ligar|liga|start|ativar|ative)\b")
_RE_SCREENSHOT_WORD = re.compile(r"\b(screenshot|printscreen|print\s+screen|captura\s+de\s+tela|tire\s+uma\s+captura)\b")
_RE_DESKTOP_WORD = re.compile(r"\b([aá]rea\s+de\s+trabalho|area\s+de\s+trabalho|desktop)\b")
_RE_SAVE_WORD = re.compile(r"\b(salvar|salva|salve|guardar)\b")

# Weather / crypto price
_RE_WEATHER = re.compile(r"\b(clima|tempo|temperatura)\b\s+em\s+(.+)$")
_RE_CRYPTO_PRICE_WORD = re.compile(r"\b(pre[cç]o|valor|cotac[aã]o)\b")
_RE_CRYPTO_ASSET = re.compile(r"\b(bitcoin|btc|ethereum|eth|solana|sol)\b")

# Wikipedia explicit
_RE_WIKIPEDIA_EXPLICIT_1 = re.compile(r"\b(wikipedia)\b\s*[:\-]?\s*(.+)$", flags=re.IGNORECASE)
_RE_WIKIPEDIA_EXPLICIT_2 = re.compile(r"\b(pesquise|pesquisa|procure|buscar|busque)\b.*\b(wikipedia)\b\s+(?:sobre\s+)?(.+)$", flags=re.IGNORECASE)

# Geo
_RE_ONDE_FICA = re.compile(r"^\s*onde\s+fica\s+(.+?)\s*[\?\!\.]?\s*$", flags=re.IGNORECASE)
_RE_GEOCODE = re.compile(r"\b(coordenadas\s+de|geocode)\b\s*[:\-]?\s*(.+)$", flags=re.IGNORECASE)
_RE_ROUTE = re.compile(r"\b(rota|como\s+ir)\b.*\b(de)\b\s+(.+?)\s+\b(para)\b\s+(.+)$", flags=re.IGNORECASE)

# FX convert
_RE_FX_CONVERT = re.compile(r"\b(converter|converta)\b\s+([\d\.,]+)\s*([A-Za-z]{3})\s+\bpara\b\s+([A-Za-z]{3})\b", flags=re.IGNORECASE)

# Country / time
_RE_COUNTRY_INFO = re.compile(r"^\s*(pa[ií]s|country)\b\s*[:\-]\s*(.+)$", flags=re.IGNORECASE)
_RE_WORLD_TIME = re.compile(r"\b(hora\s+em|time)\b\s*[:\-]?\s*([A-Za-z_+\-/]+)$", flags=re.IGNORECASE)

# News / books
_RE_NEWS = re.compile(r"\b(not[ií]cias\s+sobre|news)\b\s*[:\-]?\s*(.+)$", flags=re.IGNORECASE)
_RE_BOOK = re.compile(r"\b(livro|book)\b\s*[:\-]\s*(.+)$", flags=re.IGNORECASE)

# Holidays / Crossref
_RE_HOLIDAYS = re.compile(r"\bferiados\b\s*[:\-]?\s*(\d{4})\s+([A-Za-z]{2})\b", flags=re.IGNORECASE)
_RE_CROSSREF = re.compile(r"\b(crossref|doi\s+search)\b\s*[:\-]?\s*(.+)$", flags=re.IGNORECASE)

# Status / settings
_RE_SETTINGS_SINGLE = re.compile(r"^\s*(settings|config|configuracao|configuracoes|status|seguranca)\s*$", flags=re.IGNORECASE)
_RE_VENDOR_STATUS = re.compile(r"\bstatus\b", flags=re.IGNORECASE)
_RE_GITHUB = re.compile(r"\bgithub\b", flags=re.IGNORECASE)
_RE_CLOUDFLARE = re.compile(r"\bcloudflare\b", flags=re.IGNORECASE)
_RE_DISCORD = re.compile(r"\bdiscord\b", flags=re.IGNORECASE)
_RE_DOCKER = re.compile(r"\bdocker\b", flags=re.IGNORECASE)
_RE_ATLASSIAN = re.compile(r"\batlassian\b", flags=re.IGNORECASE)
_RE_ZOOM = re.compile(r"\bzoom\b", flags=re.IGNORECASE)
_RE_GITLAB = re.compile(r"\bgitlab\b", flags=re.IGNORECASE)
_RE_NPM = re.compile(r"\bnpm\b", flags=re.IGNORECASE)
_RE_OPENAI = re.compile(r"\bopen\s*ai\b|\bopenai\b", flags=re.IGNORECASE)

# Doctor / approvals
_RE_DOCTOR = re.compile(
    r"\b(doctor|diagnostico|diagnostico\s+do\s+ambiente|diagnostico\s+ambiente|diagnostico\s+do\s+sistema)\b",
    flags=re.IGNORECASE,
)
_RE_APPROVALS_LIST = re.compile(
    r"\b(listar|lista|ver|mostrar|exibir)\b.*\b(permissoes|permissoes\s+lembradas|permissao|aprovacoes|aprovacoes\s+lembradas|hitl)\b",
    flags=re.IGNORECASE,
)
_RE_APPROVALS_RESET = re.compile(
    r"\b(resetar|reset|limpar|apagar|zerar)\b.*\b(permissoes|permissoes\s+lembradas|aprovacoes|aprovacoes\s+lembradas|hitl)\b",
    flags=re.IGNORECASE,
)
_RE_APPROVALS_REVOKE = re.compile(
    r"\b(revogar|revoga|remover|remove)\b.*\b(permissoes|permissoes\s+lembradas|aprovacoes|aprovacoes\s+lembradas|hitl)\b",
    flags=re.IGNORECASE,
)

_RE_MEMORY_COMPACT = re.compile(r"\b(compactar|compacta|limpar|reduzir)\b.*\b(memoria|memory)\b", flags=re.IGNORECASE)

# Public APIs (finance/space/science/health)
_RE_FEAR_GREED = re.compile(r"\b(fear\s*\&\s*greed|fear\s+and\s+greed|medo\s+e\s+gan[aâ]ncia|indice\s+de\s+medo)\b", flags=re.IGNORECASE)
_RE_ISS = re.compile(r"\biss\b", flags=re.IGNORECASE)
_RE_ISS_WHERE = re.compile(r"\b(onde|posi[cç][aã]o|localiza[cç][aã]o|agora|neste\s+momento)\b", flags=re.IGNORECASE)
_RE_EARTHQUAKE = re.compile(r"\b(terremoto|terremotos|sismo|sismos|earthquake|earthquakes)\b", flags=re.IGNORECASE)
_RE_EARTHQUAKE_DAYS = re.compile(r"\b(\d{1,2})\s*(dias|dia)\b", flags=re.IGNORECASE)
_RE_EARTHQUAKE_MAG = re.compile(r"\b(mag(?:nitude)?|m)\s*(\d+(?:[\.,]\d+)?)\b", flags=re.IGNORECASE)
_RE_COVID = re.compile(r"\b(covid)\b(?:\s+(?:(no|na|em)\s+)?(.+))?$", flags=re.IGNORECASE)

_RE_OPENALEX = re.compile(r"\b(openalex)\b\s*[:\-]?\s*(.+)$", flags=re.IGNORECASE)
_RE_WIKIDATA_ENTITY = re.compile(r"\b(wikidata\s+id|entity)\b\s*[:\-]?\s*([PQ]\d+)\b", flags=re.IGNORECASE)
_RE_WIKIDATA_SEARCH = re.compile(r"\b(wikidata)\b\s*[:\-]?\s*(.+)$", flags=re.IGNORECASE)
_RE_WORLDBANK = re.compile(
    r"\b(world\s*bank|worldbank)\b\s*[:\-]?\s*([A-Za-z]{2,3})\s+([A-Za-z0-9_\.]{3,40})(?:\s+(\d{4}:\d{4}|\d{4}))?$",
    flags=re.IGNORECASE,
)

_RE_HN = re.compile(r"\bhacker\s+news\b", flags=re.IGNORECASE)
_RE_HN_SHORT = re.compile(r"\bhn\b", flags=re.IGNORECASE)
_RE_HN_FRONT = re.compile(r"\b(top|front\s*page|front)\b", flags=re.IGNORECASE)
_RE_HN_COLON = re.compile(r"\bhacker\s+news\s*[:\-]", flags=re.IGNORECASE)
_RE_SPACEX = re.compile(r"\bspacex\b", flags=re.IGNORECASE)
_RE_LATEST_LAST = re.compile(r"\b(ultimo|latest|last)\b", flags=re.IGNORECASE)
_RE_LAUNCH = re.compile(r"\b(lancamento|launch)\b", flags=re.IGNORECASE)
_RE_ARCHIVE = re.compile(r"\b(archive\s*\.\s*org|archive)\b\s*(?:search)?\s*[:\-]\s*(.+)$", flags=re.IGNORECASE)
_RE_TVMAZE = re.compile(r"\b(tv\s*maze|tvmaze)\b\s*(?:search)?\s*[:\-]\s*(.+)$", flags=re.IGNORECASE)

_RE_MEALDB = re.compile(r"\b(meal\s*db|mealdb|themealdb)\b\s*(?:search)?\s*[:\-]\s*(.+)$", flags=re.IGNORECASE)
_RE_UNIVERSITIES = re.compile(r"\b(universities|universidade|universidades)\b\s*[:\-]\s*(.+)$", flags=re.IGNORECASE)
_RE_COUNTRY_KV = re.compile(r"\b(country|pa[ií]s)\b\s*:\s*(.+)$", flags=re.IGNORECASE)

_RE_AGIFY = re.compile(r"\bagify\b\s*[:\-]\s*(.+)$", flags=re.IGNORECASE)
_RE_GENDERIZE = re.compile(r"\bgenderize\b\s*[:\-]\s*(.+)$", flags=re.IGNORECASE)
_RE_NATIONALIZE = re.compile(r"\bnationalize\b\s*[:\-]\s*(.+)$", flags=re.IGNORECASE)
_RE_CC_KV = re.compile(r"\bcc\b\s*:\s*([A-Za-z]{2})\b")

_RE_DOG = re.compile(r"\b(dog|cachorro)\b", flags=re.IGNORECASE)
_RE_IMAGE_WORD = re.compile(r"\b(imagem|foto|image|pic)\b", flags=re.IGNORECASE)

_RE_JIKAN = re.compile(r"\b(anime|jikan)\b\s*[:\-]\s*(.+)$", flags=re.IGNORECASE)

_RE_MET_OBJECT = re.compile(r"\bmet\b\s*(?:object|id)\b\s*[:\-]?\s*(\d+)\b", flags=re.IGNORECASE)
_RE_MET_SEARCH = re.compile(r"\b(met\s*museum|metmuseum|met)\b\s*[:\-]\s*(.+)$", flags=re.IGNORECASE)

_RE_XKCD_NUM = re.compile(r"\bxkcd\b\s*[:\-]\s*(\d{1,6})\b", flags=re.IGNORECASE)
_RE_XKCD = re.compile(r"\bxkcd\b", flags=re.IGNORECASE)
_RE_LATEST_WORD = re.compile(r"\b(latest|ultimo|u?ltimo|último|recente)\b", flags=re.IGNORECASE)

_RE_ITUNES = re.compile(r"\bitunes\b\s*[:\-]\s*(.+)$", flags=re.IGNORECASE)
_RE_GBOOKS = re.compile(r"\b(gbooks|googlebooks|google\s*books)\b\s*[:\-]\s*(.+)$", flags=re.IGNORECASE)
_RE_SYNONYMS = re.compile(r"\b(sinonimos|sinônimos)\b\s+de\s+([\w\-]{2,60})\b", flags=re.IGNORECASE)
_RE_DATAMUSE = re.compile(r"\bdatamuse\b\s*[:\-]\s*(.+)$", flags=re.IGNORECASE)


def _extract_path(text: str) -> str | None:
    # best-effort: quoted path or something like ./foo or data/foo
    q = re.search(r"['\"]([^'\"]{2,240})['\"]", text)
    if q:
        return q.group(1).strip()
    m = re.search(r"\b((?:\./|\.\\|data/|data\\|scratch/|scratch\\|\.vscode/|\.vscode\\)[^\s]{1,240})", text)
    if m:
        return (m.group(1) or "").strip()
    return None


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

class FearGreedIndexHandler(HeuristicHandler):
    def handle(self, user_message: str, *, context_messages: list[dict[str, str]] | None = None) -> Plan | None:
        msg = user_message
        norm = _normalize(msg)
        if re.search(
            r"\b(fear\s*\&\s*greed|fear\s+and\s+greed|medo\s+e\s+gan[aâ]ncia|indice\s+de\s+medo)\b",
            norm,
        ):
            return Plan(
                intent="finance.fear_greed_index",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="finance.fear_greed_index", args={"limit": 1})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar o índice Fear & Greed.",
            )
        return None

class ISSPositionHandler(HeuristicHandler):
    def handle(self, user_message: str, *, context_messages: list[dict[str, str]] | None = None) -> Plan | None:
        msg = user_message
        norm = _normalize(msg)
        if re.search(r"\biss\b", norm) and re.search(
            r"\b(onde|posi[cç][aã]o|localiza[cç][aã]o|agora|neste\s+momento)\b",
            norm,
        ):
            return Plan(
                intent="space.iss_position",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="space.iss_position", args={})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar a posição atual da ISS.",
            )
        return None

class EarthquakeUSGSHandler(HeuristicHandler):
    def handle(self, user_message: str, *, context_messages: list[dict[str, str]] | None = None) -> Plan | None:
        msg = user_message
        norm = _normalize(msg)
        if not re.search(r"\b(terremoto|terremotos|sismo|sismos|earthquake|earthquakes)\b", norm):
            return None

        days = 7
        m_days = re.search(r"\b(\d{1,2})\s*(dias|dia)\b", norm)
        if m_days:
            try:
                days = int(m_days.group(1) or 7)
            except Exception:
                days = 7

        min_mag = 4.5
        m_mag = re.search(r"\b(mag(?:nitude)?|m)\s*(\d+(?:[\.,]\d+)?)\b", norm)
        if m_mag:
            try:
                min_mag = float((m_mag.group(2) or "4.5").replace(",", "."))
            except Exception:
                min_mag = 4.5

        return Plan(
            intent="science.earthquake_usgs",
            user_message=msg,
            tool_calls=[
                ToolCall(
                    tool_name="science.earthquake_usgs",
                    args={"days": days, "min_magnitude": min_mag, "limit": 10},
                )
            ],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou listar terremotos recentes (USGS).",
        )

class CovidStatsHandler(HeuristicHandler):
    def handle(self, user_message: str, *, context_messages: list[dict[str, str]] | None = None) -> Plan | None:
        msg = user_message
        m = re.search(r"\b(covid)\b(?:\s+(no|na|em)\s+(.+))?$", msg, flags=re.IGNORECASE)
        if not m:
            return None
        country = (m.group(3) or "").strip().strip('"\'')
        args: dict[str, Any] = {}
        if country and _normalize(country) not in {"mundo", "global", "geral"}:
            args["country"] = country
        return Plan(
            intent="health.covid_stats",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="health.covid_stats", args=args)],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou consultar estatísticas de COVID.",
        )

class ServiceStatusHandler(HeuristicHandler):
    _SERVICE_TOOL_BY_KEYWORD: list[tuple[str, str]] = [
        ("github", "status.github"),
        ("cloudflare", "status.cloudflare"),
        ("docker", "status.docker"),
        ("atlassian", "status.atlassian"),
        ("zoom", "status.zoom"),
        ("gitlab", "status.gitlab"),
        ("npm", "status.npm"),
        ("openai", "status.openai"),
        ("open ai", "status.openai"),
    ]

    def handle(self, user_message: str, *, context_messages: list[dict[str, str]] | None = None) -> Plan | None:
        msg = user_message
        norm = _normalize(msg)
        if not re.search(r"\bstatus\b", norm):
            return None
        for keyword, tool_name in self._SERVICE_TOOL_BY_KEYWORD:
            if keyword in norm:
                return Plan(
                    intent=tool_name,
                    user_message=msg,
                    tool_calls=[ToolCall(tool_name=tool_name, args={})],
                    risk=RiskLevel.MEDIUM,
                    final_response=f"Ok — vou consultar o status de {keyword}.",
                )
        return None

class ArticSearchHandler(HeuristicHandler):
    def handle(self, user_message: str, *, context_messages: list[dict[str, str]] | None = None) -> Plan | None:
        msg = user_message
        m = re.search(
            r"\b(art\s*institute\s*of\s*chicago|aic|artic)\b\s*[:\-]\s*(.+)$",
            msg,
            flags=re.IGNORECASE,
        )
        if m and (m.group(2) or "").strip():
            q = (m.group(2) or "").strip().strip('"\'')
            return Plan(
                intent="art.artic_search",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="art.artic_search", args={"query": q, "limit": 5})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar no acervo do Art Institute of Chicago.",
            )
        return None

class ChessComHandler(HeuristicHandler):
    def handle(self, user_message: str, *, context_messages: list[dict[str, str]] | None = None) -> Plan | None:
        msg = user_message
        norm = _normalize(msg)

        m = re.search(r"\bchess\b\s*stats\s*[:\-]\s*(.+)$", msg, flags=re.IGNORECASE)
        if m and (m.group(1) or "").strip():
            user = (m.group(1) or "").strip().strip('"\'')
            return Plan(
                intent="chess.chesscom_stats",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="chess.chesscom_stats", args={"username": user})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar estatísticas no Chess.com.",
            )

        if re.search(r"\bchess\b", norm) and re.search(r"\bpuzzle\b", norm):
            return Plan(
                intent="chess.chesscom_daily_puzzle",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="chess.chesscom_daily_puzzle", args={})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar o puzzle diário do Chess.com.",
            )

        m = re.search(r"\bchess\b\s*[:\-]\s*(.+)$", msg, flags=re.IGNORECASE)
        if m and (m.group(1) or "").strip():
            user = (m.group(1) or "").strip().strip('"\'')
            return Plan(
                intent="chess.chesscom_player",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="chess.chesscom_player", args={"username": user})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar o perfil do jogador no Chess.com.",
            )
        return None

class OpenBreweryDBHandler(HeuristicHandler):
    def handle(self, user_message: str, *, context_messages: list[dict[str, str]] | None = None) -> Plan | None:
        msg = user_message
        m = re.search(r"\b(cervejarias|brewery|breweries)\b\s*[:\-]\s*(.+)$", msg, flags=re.IGNORECASE)
        if m and (m.group(2) or "").strip():
            q = (m.group(2) or "").strip().strip('"\'')
            return Plan(
                intent="drink.openbrewerydb_search",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="drink.openbrewerydb_search", args={"query": q, "limit": 5})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar cervejarias (Open Brewery DB).",
            )
        return None

class DeckOfCardsHandler(HeuristicHandler):
    def handle(self, user_message: str, *, context_messages: list[dict[str, str]] | None = None) -> Plan | None:
        msg = user_message
        m = re.search(r"\b(cartas|cards)\b\s*[:\-]\s*(\d{1,2})\b", msg, flags=re.IGNORECASE)
        if m:
            try:
                n = int(m.group(2) or 1)
            except Exception:
                n = 1
            return Plan(
                intent="fun.deck_draw",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="fun.deck_draw", args={"count": n})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou sacar cartas (Deck of Cards API).",
            )
        return None


def _infer_coin_from_context(ctx: list[dict[str, Any]] | None) -> str | None:
    # Back-compat: delega para `_infer_subject_from_context`.
    return _infer_subject_from_context(ctx)  # type: ignore[arg-type]


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
            final_response="Posso ajudar — o que você quer fazer com esse número?",
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
class StatusHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        msg = user_message.strip()

        if _RE_SETTINGS_SINGLE.fullmatch(norm or ""):
            return Plan(
                intent="core.show_settings",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="core.show_settings", args={})],
                risk=RiskLevel.LOW,
                final_response="Aqui estão as configurações efetivas.",
            )

        if not _RE_VENDOR_STATUS.search(norm):
            return None

        vendor_map: list[tuple[re.Pattern[str], str, str]] = [
            (_RE_GITHUB, "status.github", "Ok — vou consultar o status do GitHub."),
            (_RE_CLOUDFLARE, "status.cloudflare", "Ok — vou consultar o status do Cloudflare."),
            (_RE_DISCORD, "status.discord", "Ok — vou consultar o status do Discord."),
            (_RE_DOCKER, "status.docker", "Ok — vou consultar o status do Docker."),
            (_RE_ATLASSIAN, "status.atlassian", "Ok — vou consultar o status da Atlassian."),
            (_RE_ZOOM, "status.zoom", "Ok — vou consultar o status do Zoom."),
            (_RE_GITLAB, "status.gitlab", "Ok — vou consultar o status do GitLab."),
            (_RE_NPM, "status.npm", "Ok — vou consultar o status do npm."),
            (_RE_OPENAI, "status.openai", "Ok — vou consultar o status da OpenAI."),
        ]

        for pat, intent, final_response in vendor_map:
            if pat.search(norm):
                return Plan(
                    intent=intent,
                    user_message=msg,
                    tool_calls=[ToolCall(tool_name=intent, args={})],
                    risk=RiskLevel.MEDIUM,
                    final_response=final_response,
                )

        return None


@dataclass(frozen=True)
class CoreOpsHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        msg = user_message.strip()

        if (norm in {"doctor", "diagnostico", "diagnostico do ambiente", "diagnostico ambiente", "diagnostico do sistema"}) or _RE_DOCTOR.search(norm):
            return Plan(
                intent="core.doctor",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="core.doctor", args={})],
                risk=RiskLevel.LOW,
                final_response="Ok — vou rodar o diagnóstico do ambiente.",
            )

        if _RE_APPROVALS_LIST.search(norm):
            return Plan(
                intent="core.approvals_list",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="core.approvals_list", args={})],
                risk=RiskLevel.LOW,
                final_response="Ok — aqui está a lista de permissões lembradas.",
            )

        if _RE_APPROVALS_RESET.search(norm):
            return Plan(
                intent="core.approvals_reset",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="core.approvals_reset", args={})],
                risk=RiskLevel.HIGH,
                final_response="Ok — vou resetar as permissões lembradas (requer aprovação).",
            )

        if _RE_APPROVALS_REVOKE.search(norm):
            contains = ""
            m_quote = re.search(r"['\"]([^'\"]{2,180})['\"]", msg)
            if m_quote:
                contains = (m_quote.group(1) or "").strip()
            else:
                m_contains = re.search(r"\bcontendo\b\s+([^\n]{2,180})", norm)
                if m_contains:
                    contains = (m_contains.group(1) or "").strip(" .,:;!?\"'")

            args = {"contains": contains} if contains else {}
            return Plan(
                intent="core.approvals_revoke",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="core.approvals_revoke", args=args)],
                risk=RiskLevel.HIGH,
                final_response="Ok — vou revogar permissões lembradas (requer aprovação).",
            )

        return None


@dataclass(frozen=True)
class MemoryCompactHandler:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        msg = user_message.strip()
        if not _RE_MEMORY_COMPACT.search(norm):
            return None
        return Plan(
            intent="core.memory_compact",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="core.memory_compact", args={"keep_last": 5000, "archive": True})],
            risk=RiskLevel.HIGH,
            final_response="Ok — vou compactar a memória (mantendo os eventos mais recentes).",
        )


@dataclass(frozen=True)
class PublicApisHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        msg = user_message.strip()

        if _RE_FEAR_GREED.search(norm):
            return Plan(
                intent="finance.fear_greed_index",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="finance.fear_greed_index", args={"limit": 1})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar o índice Fear & Greed.",
            )

        if _RE_ISS.search(norm) and _RE_ISS_WHERE.search(norm):
            return Plan(
                intent="space.iss_position",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="space.iss_position", args={})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar a posição atual da ISS.",
            )

        if _RE_EARTHQUAKE.search(norm):
            days = 7
            m_days = _RE_EARTHQUAKE_DAYS.search(norm)
            if m_days:
                try:
                    days = int(m_days.group(1) or 7)
                except Exception:
                    days = 7

            min_mag = 4.5
            m_mag = _RE_EARTHQUAKE_MAG.search(norm)
            if m_mag:
                try:
                    min_mag = float((m_mag.group(2) or "4.5").replace(",", "."))
                except Exception:
                    min_mag = 4.5

            return Plan(
                intent="science.earthquake_usgs",
                user_message=msg,
                tool_calls=[
                    ToolCall(
                        tool_name="science.earthquake_usgs",
                        args={"days": days, "min_magnitude": min_mag, "limit": 10},
                    )
                ],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou listar terremotos recentes (USGS).",
            )

        m = _RE_COVID.search(msg)
        if m:
            country = (m.group(3) or "").strip().strip("\"'")
            args: dict[str, object] = {}
            if not country:
                # aceita "covid global" / "covid mundo" / "covid geral"
                tail = (msg.split("covid", 1)[1] if "covid" in msg.lower() else "").strip(" :.-").strip()
                if tail and tail.casefold() not in {"mundo", "global", "geral"}:
                    args["country"] = tail
            else:
                if country.casefold().strip() not in {"mundo", "global", "geral"}:
                    args["country"] = country
            return Plan(
                intent="health.covid_stats",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="health.covid_stats", args=args)],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou consultar estatísticas de COVID.",
            )

        m = _RE_OPENALEX.search(msg)
        if m and (m.group(2) or "").strip():
            q = (m.group(2) or "").strip().strip("\"'")
            if q:
                return Plan(
                    intent="knowledge.openalex_works_search",
                    user_message=msg,
                    tool_calls=[ToolCall(tool_name="knowledge.openalex_works_search", args={"query": q, "max_results": 5})],
                    risk=RiskLevel.MEDIUM,
                    final_response="Ok — vou buscar works/papers no OpenAlex.",
                )

        m = _RE_WIKIDATA_ENTITY.search(msg)
        if m and (m.group(2) or "").strip():
            ent = (m.group(2) or "").strip().upper()
            return Plan(
                intent="knowledge.wikidata_entity",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="knowledge.wikidata_entity", args={"id": ent})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou baixar dados da entidade do Wikidata.",
            )

        m = _RE_WIKIDATA_SEARCH.search(msg)
        if m and (m.group(2) or "").strip():
            q = (m.group(2) or "").strip().strip("\"'")
            if q:
                return Plan(
                    intent="knowledge.wikidata_search",
                    user_message=msg,
                    tool_calls=[ToolCall(tool_name="knowledge.wikidata_search", args={"query": q, "lang": "pt", "limit": 5})],
                    risk=RiskLevel.MEDIUM,
                    final_response="Ok — vou buscar entidades no Wikidata.",
                )

        m = _RE_WORLDBANK.search(msg)
        if m:
            cc = (m.group(2) or "").strip().upper()
            ind = (m.group(3) or "").strip().upper()
            date = (m.group(4) or "").strip()
            args: dict[str, object] = {"country_code": cc, "indicator": ind}
            if date:
                args["date"] = date
            return Plan(
                intent="data.worldbank_indicator",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="data.worldbank_indicator", args=args)],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou consultar o indicador no World Bank.",
            )

        if (_RE_HN.search(norm) and _RE_HN_FRONT.search(norm)) or (_RE_HN_SHORT.search(norm) and _RE_HN_FRONT.search(norm)):
            return Plan(
                intent="news.hackernews_front_page",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="news.hackernews_front_page", args={"limit": 10})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou pegar a front page do Hacker News.",
            )

        if _RE_SPACEX.search(norm) and _RE_LATEST_LAST.search(norm) and _RE_LAUNCH.search(norm):
            return Plan(
                intent="space.spacex_latest_launch",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="space.spacex_latest_launch", args={})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar o último lançamento da SpaceX.",
            )

        m = _RE_ARCHIVE.search(msg)
        if m and (m.group(2) or "").strip():
            q = (m.group(2) or "").strip().strip("\"'")
            if q:
                return Plan(
                    intent="archive.archiveorg_search",
                    user_message=msg,
                    tool_calls=[ToolCall(tool_name="archive.archiveorg_search", args={"query": q, "limit": 5})],
                    risk=RiskLevel.MEDIUM,
                    final_response="Ok — vou buscar no Archive.org.",
                )

        m = _RE_TVMAZE.search(msg)
        if m and (m.group(2) or "").strip():
            q = (m.group(2) or "").strip().strip("\"'")
            if q:
                return Plan(
                    intent="media.tvmaze_search",
                    user_message=msg,
                    tool_calls=[ToolCall(tool_name="media.tvmaze_search", args={"query": q, "limit": 5})],
                    risk=RiskLevel.MEDIUM,
                    final_response="Ok — vou buscar séries no TVMaze.",
                )

        m = _RE_MEALDB.search(msg)
        if m and (m.group(2) or "").strip():
            q = (m.group(2) or "").strip().strip("\"'")
            if q:
                return Plan(
                    intent="food.meal_search",
                    user_message=msg,
                    tool_calls=[ToolCall(tool_name="food.meal_search", args={"query": q, "limit": 5})],
                    risk=RiskLevel.MEDIUM,
                    final_response="Ok — vou buscar receitas no TheMealDB.",
                )

        m = _RE_UNIVERSITIES.search(msg)
        if m and (m.group(2) or "").strip():
            q = (m.group(2) or "").strip().strip("\"'")
            if q:
                country: str | None = None
                m_country = _RE_COUNTRY_KV.search(q)
                if m_country:
                    country = (m_country.group(2) or "").strip().strip("\"'")
                    q = re.sub(_RE_COUNTRY_KV, "", q).strip().rstrip("|;")

                q = q.strip().rstrip("|;")

                args: dict[str, object] = {"name": q, "limit": 10}
                if country:
                    args["country"] = country
                return Plan(
                    intent="edu.universities_search",
                    user_message=msg,
                    tool_calls=[ToolCall(tool_name="edu.universities_search", args=args)],
                    risk=RiskLevel.MEDIUM,
                    final_response="Ok — vou buscar universidades.",
                )

        m = _RE_AGIFY.search(msg)
        if m and (m.group(1) or "").strip():
            q = (m.group(1) or "").strip().strip("\"'")
            cc: str | None = None
            m_cc = _RE_CC_KV.search(q)
            if m_cc:
                cc = (m_cc.group(1) or "").strip().upper()
                q = re.sub(_RE_CC_KV, "", q).strip().rstrip("|;")
            args: dict[str, object] = {"name": q}
            if cc:
                args["country_code"] = cc
            return Plan(
                intent="people.agify_name",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="people.agify_name", args=args)],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou estimar idade provável (Agify).",
            )

        m = _RE_GENDERIZE.search(msg)
        if m and (m.group(1) or "").strip():
            q = (m.group(1) or "").strip().strip("\"'")
            cc: str | None = None
            m_cc = _RE_CC_KV.search(q)
            if m_cc:
                cc = (m_cc.group(1) or "").strip().upper()
                q = re.sub(_RE_CC_KV, "", q).strip().rstrip("|;")
            args: dict[str, object] = {"name": q}
            if cc:
                args["country_code"] = cc
            return Plan(
                intent="people.genderize_name",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="people.genderize_name", args=args)],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou estimar gênero provável (Genderize).",
            )

        m = _RE_NATIONALIZE.search(msg)
        if m and (m.group(1) or "").strip():
            q = (m.group(1) or "").strip().strip("\"'")
            return Plan(
                intent="people.nationalize_name",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="people.nationalize_name", args={"name": q, "limit": 5})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou estimar nacionalidade provável (Nationalize).",
            )

        if _RE_DOG.search(norm) and _RE_IMAGE_WORD.search(norm):
            return Plan(
                intent="fun.dog_image",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="fun.dog_image", args={})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar uma imagem aleatória de cachorro.",
            )

        m = _RE_JIKAN.search(msg)
        if m and (m.group(2) or "").strip():
            q = (m.group(2) or "").strip().strip("\"'")
            if q:
                return Plan(
                    intent="anime.jikan_search",
                    user_message=msg,
                    tool_calls=[ToolCall(tool_name="anime.jikan_search", args={"query": q, "limit": 5})],
                    risk=RiskLevel.MEDIUM,
                    final_response="Ok — vou buscar animes (Jikan/MyAnimeList).",
                )

        m = _RE_MET_OBJECT.search(msg)
        if m:
            oid = int(m.group(1))
            return Plan(
                intent="art.met_object",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="art.met_object", args={"object_id": oid})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar o item do Met Museum.",
            )

        m = _RE_MET_SEARCH.search(msg)
        if m and (m.group(2) or "").strip():
            q = (m.group(2) or "").strip().strip("\"'")
            if q:
                return Plan(
                    intent="art.met_search",
                    user_message=msg,
                    tool_calls=[ToolCall(tool_name="art.met_search", args={"query": q, "limit": 5})],
                    risk=RiskLevel.MEDIUM,
                    final_response="Ok — vou buscar no acervo do Met Museum.",
                )

        m = _RE_XKCD_NUM.search(msg)
        if m:
            return Plan(
                intent="fun.xkcd_comic",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="fun.xkcd_comic", args={"num": int(m.group(1))})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar essa tirinha do xkcd.",
            )

        if _RE_XKCD.search(norm):
            if _RE_LATEST_WORD.search(norm) or norm.strip() == "xkcd":
                return Plan(
                    intent="fun.xkcd_latest",
                    user_message=msg,
                    tool_calls=[ToolCall(tool_name="fun.xkcd_latest", args={})],
                    risk=RiskLevel.MEDIUM,
                    final_response="Ok — vou buscar a última tirinha do xkcd.",
                )

        m = _RE_ITUNES.search(msg)
        if m and (m.group(1) or "").strip():
            q = (m.group(1) or "").strip().strip("\"'")
            if q:
                return Plan(
                    intent="music.itunes_search",
                    user_message=msg,
                    tool_calls=[ToolCall(tool_name="music.itunes_search", args={"query": q, "media": "music", "limit": 5})],
                    risk=RiskLevel.MEDIUM,
                    final_response="Ok — vou buscar no iTunes.",
                )

        m = _RE_GBOOKS.search(msg)
        if m and (m.group(2) or "").strip():
            q = (m.group(2) or "").strip().strip("\"'")
            if q:
                return Plan(
                    intent="books.googlebooks_search",
                    user_message=msg,
                    tool_calls=[ToolCall(tool_name="books.googlebooks_search", args={"query": q, "limit": 5})],
                    risk=RiskLevel.MEDIUM,
                    final_response="Ok — vou buscar livros no Google Books.",
                )

        m = _RE_SYNONYMS.search(msg)
        if m and (m.group(2) or "").strip():
            q = (m.group(2) or "").strip().strip("\"'")
            if q:
                return Plan(
                    intent="language.datamuse_related_words",
                    user_message=msg,
                    tool_calls=[
                        ToolCall(
                            tool_name="language.datamuse_related_words",
                            args={"query": q, "relation": "rel_syn", "max_results": 10},
                        )
                    ],
                    risk=RiskLevel.MEDIUM,
                    final_response="Ok — vou buscar sinônimos/relacionados (Datamuse).",
                )

        m = _RE_DATAMUSE.search(msg)
        if m and (m.group(1) or "").strip():
            q = (m.group(1) or "").strip().strip("\"'")
            if q:
                return Plan(
                    intent="language.datamuse_related_words",
                    user_message=msg,
                    tool_calls=[
                        ToolCall(
                            tool_name="language.datamuse_related_words",
                            args={"query": q, "relation": "ml", "max_results": 10},
                        )
                    ],
                    risk=RiskLevel.MEDIUM,
                    final_response="Ok — vou buscar palavras relacionadas (Datamuse).",
                )

        return None


@dataclass(frozen=True)
class MorePublicApisHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        msg = user_message.strip()

        # OSV query por pacote+versão — explícito
        m = re.search(
            r"\b(osv)\b\s*[:\-]?\s*(PyPI|pypi|pip|npm|node|crates(?:\.io)?|rust|RubyGems|rubygems|Maven|maven|NuGet|nuget|Go|go)\s+([^\s]{1,120})\s+([^\s]{1,60})\b",
            msg,
            flags=re.IGNORECASE,
        )
        if m:
            eco = (m.group(2) or "").strip()
            name = (m.group(3) or "").strip()
            ver = (m.group(4) or "").strip()
            return Plan(
                intent="sec.osv_query",
                user_message=msg,
                tool_calls=[
                    ToolCall(
                        tool_name="sec.osv_query",
                        args={"ecosystem": eco, "name": name, "version": ver, "limit": 10},
                    )
                ],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou checar vulnerabilidades para essa versão (OSV.dev).",
            )

        # PyPI project — explícito
        m = re.search(r"\b(pypi|pip)\b\s*[:\-]?\s*([A-Za-z0-9_\.\-]{1,80})\b", msg, flags=re.IGNORECASE)
        if m and (m.group(2) or "").strip():
            pkg = (m.group(2) or "").strip()
            return Plan(
                intent="pkg.pypi_project",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="pkg.pypi_project", args={"name": pkg})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar metadados do projeto no PyPI.",
            )

        # npm package — explícito
        m = re.search(r"\b(npm)\b\s*[:\-]?\s*([^\s]{1,160})\b", msg, flags=re.IGNORECASE)
        if m and (m.group(2) or "").strip() and not re.search(r"\bnpm\s+downloads\b", norm):
            pkg = (m.group(2) or "").strip()
            return Plan(
                intent="pkg.npm_package",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="pkg.npm_package", args={"name": pkg})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar metadados do pacote no npm registry.",
            )

        # crates.io crate — explícito
        m = re.search(r"\b(crates(?:\.io)?)\b\s*[:\-]?\s*([A-Za-z0-9_\-]{1,64})\b", msg, flags=re.IGNORECASE)
        if m and (m.group(2) or "").strip():
            crate = (m.group(2) or "").strip()
            return Plan(
                intent="pkg.cratesio_crate",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="pkg.cratesio_crate", args={"name": crate})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar metadados do crate no crates.io.",
            )

        # DNS resolve — explícito
        m = re.search(
            r"\b(dns|resolve)\b\s*[:\-]?\s*([A-Za-z0-9\-\.]{1,253})(?:\s+(A|AAAA|CNAME|MX|TXT))?$",
            msg,
            flags=re.IGNORECASE,
        )
        if m and (m.group(2) or "").strip():
            host = (m.group(2) or "").strip().strip('"\'').rstrip(".")
            rtype = (m.group(3) or "A").strip().upper()
            return Plan(
                intent="net.dns_google_resolve",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="net.dns_google_resolve", args={"name": host, "type": rtype})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou resolver DNS via Google (DoH).",
            )

        # RDAP domain — explícito
        m = re.search(
            r"\b(rdap\s+domain|rdap|whois)\b\s*[:\-]?\s*([A-Za-z0-9\-\.]{1,253}\.[A-Za-z]{2,24})\b",
            msg,
            flags=re.IGNORECASE,
        )
        if m and (m.group(2) or "").strip():
            domain = (m.group(2) or "").strip().strip('"\'').rstrip(".")
            return Plan(
                intent="net.rdap_domain",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="net.rdap_domain", args={"domain": domain})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou consultar RDAP para esse domínio.",
            )

        # RDAP IP — explícito
        m = re.search(r"\b(rdap\s+ip|whois\s+ip|rdap)\b\s*[:\-]?\s*(\d{1,3}(?:\.\d{1,3}){3})\b", msg, flags=re.IGNORECASE)
        if m and (m.group(2) or "").strip():
            ip = (m.group(2) or "").strip()
            return Plan(
                intent="net.rdap_ip",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="net.rdap_ip", args={"ip": ip})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou consultar RDAP para esse IP.",
            )

        # BGPView IP — explícito
        m = re.search(r"\b(bgp\s*ip|bgp)\b\s*[:\-]?\s*(\d{1,3}(?:\.\d{1,3}){3})\b", msg, flags=re.IGNORECASE)
        if m and (m.group(2) or "").strip():
            ip = (m.group(2) or "").strip()
            return Plan(
                intent="net.bgpview_ip",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="net.bgpview_ip", args={"ip": ip})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou consultar dados BGP/ASN para esse IP.",
            )

        # BGPView ASN — explícito (evita capturar "ripestat asn" / "peeringdb asn")
        m = re.search(r"\b(bgp\s*asn|asn\s*[:\-]?)\b\s*(?:AS)?(\d{1,10})\b", msg, flags=re.IGNORECASE)
        if m and (m.group(2) or "").strip() and not re.search(r"\b(ripestat|ripe\s*stat|peeringdb|peering\s*db)\b", norm):
            asn = (m.group(2) or "").strip()
            return Plan(
                intent="net.bgpview_asn",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="net.bgpview_asn", args={"asn": asn})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou consultar informações desse ASN.",
            )

        # "meu ip"
        if re.search(r"\bmeu\s+ip\b", norm):
            return Plan(
                intent="net.ip_info",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="net.ip_info", args={})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou consultar seu IP público.",
            )

        # asn: 15169 (BGPView)
        m = re.search(r"\basn\b\s*[:\-]?\s*(?:AS)?(\d{1,10})\b", msg, flags=re.IGNORECASE)
        if m and (m.group(1) or "").strip() and not re.search(r"\b(ripestat|ripe\s*stat|peeringdb|peering\s*db)\b", norm):
            asn = (m.group(1) or "").strip()
            return Plan(
                intent="net.bgpview_asn",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="net.bgpview_asn", args={"asn": asn})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou consultar informações desse ASN.",
            )

        # random user
        if re.search(r"\b(pessoa\s+aleat[oó]ria|random\s+user)\b", norm):
            return Plan(
                intent="people.random_user",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="people.random_user", args={})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou gerar uma pessoa aleatória.",
            )

        # qr
        m = re.search(r"\bqr\b\s*[:\-]?\s*(https?://\S+)", msg, flags=re.IGNORECASE)
        if m and (m.group(1) or "").strip():
            url = (m.group(1) or "").strip()
            return Plan(
                intent="utils.qr_code_url",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="utils.qr_code_url", args={"url": url})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou gerar o QR code.",
            )

        # osv vuln by CVE
        if re.fullmatch(r"cve-\d{4}-\d{4,7}", norm, flags=re.IGNORECASE):
            return Plan(
                intent="sec.osv_vuln",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="sec.osv_vuln", args={"vuln_id": norm.upper()})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou consultar o OSV para esse CVE.",
            )

        # npm downloads last week
        m = re.search(r"\bnpm\s+downloads\b\s*[:\-]?\s*([a-zA-Z0-9_\-\.]{1,80})\b", msg, flags=re.IGNORECASE)
        if m and (m.group(1) or "").strip():
            pkg = (m.group(1) or "").strip()
            return Plan(
                intent="pkg.npm_downloads_last_week",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="pkg.npm_downloads_last_week", args={"package": pkg})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar downloads da última semana (npm).",
            )

        # npm: <pkg>
        m = re.search(r"\bnpm\b\s*[:\-]?\s*([a-zA-Z0-9_\-\.]{1,80})\b", msg, flags=re.IGNORECASE)
        if m and (m.group(1) or "").strip():
            pkg = (m.group(1) or "").strip()
            return Plan(
                intent="pkg.npm_package",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="pkg.npm_package", args={"package": pkg})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou consultar o pacote no npm.",
            )

        # artic
        m = re.search(r"\bartic\b\s*[:\-]?\s*(.+)$", msg, flags=re.IGNORECASE)
        if m and (m.group(1) or "").strip():
            q = (m.group(1) or "").strip().strip('"\'')
            return Plan(
                intent="art.artic_search",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="art.artic_search", args={"query": q, "limit": 5})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar no Art Institute of Chicago.",
            )

        # chess.com
        m = re.search(r"\bchess\b\s*[:\-]?\s*([\w\-]{1,40})\b", msg, flags=re.IGNORECASE)
        if m and (m.group(1) or "").strip() and not re.search(r"\b(stats|puzzle)\b", norm):
            username = (m.group(1) or "").strip()
            return Plan(
                intent="chess.chesscom_player",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="chess.chesscom_player", args={"username": username})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar o perfil no Chess.com.",
            )

        m = re.search(r"\bchess\b\s+stats\b\s*[:\-]?\s*([\w\-]{1,40})\b", msg, flags=re.IGNORECASE)
        if m and (m.group(1) or "").strip():
            username = (m.group(1) or "").strip()
            return Plan(
                intent="chess.chesscom_stats",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="chess.chesscom_stats", args={"username": username})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar estatísticas no Chess.com.",
            )

        if re.search(r"\bchess\b.*\b(puzzle|daily\s+puzzle)\b", norm):
            return Plan(
                intent="chess.chesscom_daily_puzzle",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="chess.chesscom_daily_puzzle", args={})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar o puzzle diário do Chess.com.",
            )

        # openbrewerydb
        m = re.search(r"\b(cervejarias|brewery|breweries)\b\s*[:\-]?\s*(.+)$", msg, flags=re.IGNORECASE)
        if m and (m.group(2) or "").strip():
            q = (m.group(2) or "").strip().strip('"\'')
            return Plan(
                intent="drink.openbrewerydb_search",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="drink.openbrewerydb_search", args={"query": q, "per_page": 5})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar cervejarias.",
            )

        # gutendex
        m = re.search(r"\b(gutenberg|gutendex)\b\s*[:\-]?\s*(.+)$", msg, flags=re.IGNORECASE)
        if m and (m.group(2) or "").strip():
            q = (m.group(2) or "").strip().strip('"\'')
            return Plan(
                intent="books.gutendex_search",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="books.gutendex_search", args={"query": q, "limit": 5})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar livros no Gutenberg.",
            )

        # openfoodfacts
        m = re.search(r"\bopenfoodfacts\b\s*[:\-]?\s*(.+)$", msg, flags=re.IGNORECASE)
        if m and (m.group(1) or "").strip():
            q = (m.group(1) or "").strip().strip('"\'')
            return Plan(
                intent="data.openfoodfacts_search",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="data.openfoodfacts_search", args={"query": q, "page_size": 5})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar no OpenFoodFacts.",
            )

        # sunrise/sunset
        m = re.search(r"\bsunrise\b\s*[:\-]?\s*([-+]?\d{1,2}(?:\.\d+)?)\s*,\s*([-+]?\d{1,3}(?:\.\d+)?)\b", msg, flags=re.IGNORECASE)
        if m and (m.group(1) or "").strip() and (m.group(2) or "").strip():
            lat = float(m.group(1))
            lng = float(m.group(2))
            return Plan(
                intent="time.sunrise_sunset",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="time.sunrise_sunset", args={"lat": lat, "lng": lng})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar nascer/pôr do sol.",
            )

        # viacep
        m = re.search(r"\bcep\b\s*[:\-]?\s*(\d{5}-?\d{3})\b", msg, flags=re.IGNORECASE)
        if m and (m.group(1) or "").strip():
            cep = (m.group(1) or "").strip()
            return Plan(
                intent="br.viacep_lookup",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="br.viacep_lookup", args={"cep": cep})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou consultar o ViaCEP.",
            )

        # RIPEstat IP — explícito
        m = re.search(r"\b(ripe\s*stat|ripestat)\b\s*(?:ip)?\s*[:\-]?\s*(\d{1,3}(?:\.\d{1,3}){3})\b", msg, flags=re.IGNORECASE)
        if m and (m.group(2) or "").strip():
            ip = (m.group(2) or "").strip()
            return Plan(
                intent="net.ripestat_ip",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="net.ripestat_ip", args={"ip": ip})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou consultar o RIPEstat para esse IP.",
            )

        # RIPEstat ASN — explícito
        m = re.search(r"\b(ripe\s*stat|ripestat)\b\s*(?:asn)?\s*[:\-]?\s*(?:AS)?(\d{1,10})\b", msg, flags=re.IGNORECASE)
        if m and (m.group(2) or "").strip():
            asn = (m.group(2) or "").strip()
            return Plan(
                intent="net.ripestat_asn",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="net.ripestat_asn", args={"asn": asn})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou consultar o RIPEstat para esse ASN.",
            )

        # PeeringDB ASN — explícito
        m = re.search(r"\b(peering\s*db|peeringdb)\b\s*[:\-]?\s*(?:asn\s*[:\-]?\s*)?(?:AS)?(\d{1,10})\b", msg, flags=re.IGNORECASE)
        if m and (m.group(2) or "").strip():
            asn = (m.group(2) or "").strip()
            return Plan(
                intent="net.peeringdb_asn",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="net.peeringdb_asn", args={"asn": asn})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou consultar o PeeringDB para esse ASN.",
            )

        # crt.sh — explícito
        m = re.search(r"\b(crt\s*sh|crtsh|certificados|certificates)\b\s*[:\-]?\s*(.+)$", msg, flags=re.IGNORECASE)
        if m and (m.group(2) or "").strip():
            q = (m.group(2) or "").strip().strip('"\'')
            return Plan(
                intent="sec.crtsh_search",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="sec.crtsh_search", args={"query": q, "limit": 10})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar certificados em CT (crt.sh).",
            )

        # CISA KEV — explícito
        m = re.search(r"\b(cisa\s+kev|kev)\b\s*[:\-]?\s*(.+)$", msg, flags=re.IGNORECASE)
        if m and (m.group(2) or "").strip():
            q = (m.group(2) or "").strip().strip('"\'')
            return Plan(
                intent="sec.cisa_kev_search",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="sec.cisa_kev_search", args={"query": q, "limit": 10})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar no catálogo CISA KEV.",
            )

        # URLhaus — explícito
        m = re.search(r"\burlhaus\b\s*(?:url)?\s*[:\-]?\s*(https?://\S+)\s*$", msg, flags=re.IGNORECASE)
        if m and (m.group(1) or "").strip():
            u = (m.group(1) or "").strip().strip('"\'')
            return Plan(
                intent="sec.urlhaus_url",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="sec.urlhaus_url", args={"url": u})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou consultar o URLhaus para essa URL.",
            )

        m = re.search(r"\burlhaus\b\s*(?:host|dom[íi]nio|domain)\s*[:\-]?\s*([A-Za-z0-9\-\.]{1,253})\b", msg, flags=re.IGNORECASE)
        if m and (m.group(1) or "").strip():
            host = (m.group(1) or "").strip().strip('"\'').rstrip(".")
            return Plan(
                intent="sec.urlhaus_host",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="sec.urlhaus_host", args={"host": host})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou consultar o URLhaus para esse host.",
            )

        # ThreatFox IOC — explícito
        m = re.search(r"\b(threat\s*fox|threatfox)\b\s*(?:ioc)?\s*[:\-]?\s*(.+)$", msg, flags=re.IGNORECASE)
        if m and (m.group(2) or "").strip():
            ioc = (m.group(2) or "").strip().strip('"\'')
            return Plan(
                intent="sec.threatfox_ioc_search",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="sec.threatfox_ioc_search", args={"ioc": ioc, "limit": 10})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar esse IOC no ThreatFox.",
            )

        # Feodo Tracker — explícito
        if re.search(r"\bfeodo\b", norm) and re.search(r"\btracker\b", norm):
            return Plan(
                intent="sec.feodotracker_ip_blocklist",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="sec.feodotracker_ip_blocklist", args={"limit": 20})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar a blocklist do Feodo Tracker.",
            )

        # Hashlookup — explícito
        if re.search(r"\bhash\s*lookup\b|\bhashlookup\b", norm):
            algo = ""
            if re.search(r"\bsha\s*256\b|\bsha256\b", norm):
                algo = "sha256"
            elif re.search(r"\bsha\s*1\b|\bsha1\b", norm):
                algo = "sha1"
            elif re.search(r"\bmd5\b", norm):
                algo = "md5"

            mh = re.search(r"\b([0-9a-fA-F]{32}|[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\b", msg)
            if mh and (mh.group(1) or "").strip():
                h = (mh.group(1) or "").strip().lower()
                if not algo:
                    algo = {32: "md5", 40: "sha1", 64: "sha256"}.get(len(h), "")
                if algo:
                    return Plan(
                        intent="sec.hashlookup",
                        user_message=msg,
                        tool_calls=[ToolCall(tool_name="sec.hashlookup", args={"algorithm": algo, "hash": h})],
                        risk=RiskLevel.MEDIUM,
                        final_response="Ok — vou consultar esse hash no Hashlookup (CIRCL).",
                    )

        return None


@dataclass(frozen=True)
class FunAndMediaHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        msg = user_message.strip()

        # piada
        if re.search(r"\b(piada|joke)\b", norm):
            return Plan(
                intent="fun.joke",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="fun.joke", args={})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou contar uma piada.",
            )

        # trivia
        if re.search(r"\b(trivia|quiz)\b", norm):
            return Plan(
                intent="fun.trivia",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="fun.trivia", args={"amount": 5, "type": "multiple"})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou pegar perguntas de trivia.",
            )

        # quote
        if re.search(r"\b(quote|cita[cç][aã]o)\b", norm):
            return Plan(
                intent="fun.quote_random",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="fun.quote_random", args={})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar uma citação aleatória.",
            )

        # advice
        if re.search(r"\b(conselho|advice)\b", norm):
            return Plan(
                intent="fun.advice",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="fun.advice", args={})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar um conselho.",
            )

        # bored activity
        if re.search(r"\b(entediad[oa]|bored)\b", norm):
            return Plan(
                intent="fun.bored_activity",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="fun.bored_activity", args={})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou sugerir uma atividade.",
            )

        # fox image
        if re.search(r"\b(raposa|fox)\b", norm):
            return Plan(
                intent="fun.fox_image",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="fun.fox_image", args={})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar uma imagem de raposa.",
            )

        # duck image
        if re.search(r"\b(pato|duck)\b", norm) and re.search(r"\b(imagem|image)\b", norm):
            return Plan(
                intent="fun.duck_image",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="fun.duck_image", args={})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar uma imagem de pato.",
            )

        # cat fact
        if re.search(r"\b(cat\s*fact|fato\s+de\s+gato)\b", norm):
            return Plan(
                intent="fun.cat_fact",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="fun.cat_fact", args={})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar um fato sobre gatos.",
            )

        # deck draw
        m = re.search(r"\b(cartas|deck)\b\s*[:\-]?\s*(\d{1,2})\b", norm)
        if m and (m.group(2) or "").strip():
            n = int(m.group(2))
            return Plan(
                intent="fun.deck_draw",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="fun.deck_draw", args={"count": n})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou sacar cartas.",
            )

        # dadjoke / jokeapi
        if re.search(r"\b(dadjoke)\b", norm):
            return Plan(
                intent="fun.dadjoke",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="fun.dadjoke", args={})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar um dad joke.",
            )
        if re.search(r"\b(jokeapi)\b", norm):
            return Plan(
                intent="fun.jokeapi",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="fun.jokeapi", args={})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar uma piada (JokeAPI).",
            )

        # scryfall
        m = re.search(r"\b(scryfall)\b\s*[:\-]?\s*(.+)$", msg, flags=re.IGNORECASE)
        if m and (m.group(2) or "").strip():
            q = (m.group(2) or "").strip().strip('"\'')
            return Plan(
                intent="cards.scryfall_search",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="cards.scryfall_search", args={"query": q})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar cartas (Scryfall).",
            )
        if re.search(r"\b(mtg\s*random)\b", norm):
            return Plan(
                intent="cards.scryfall_random",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="cards.scryfall_random", args={})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar uma carta aleatória (Scryfall).",
            )

        # rickmorty
        m = re.search(r"\b(rickmorty)\b\s*[:\-]?\s*(.+)$", msg, flags=re.IGNORECASE)
        if m and (m.group(2) or "").strip():
            q = (m.group(2) or "").strip().strip('"\'')
            return Plan(
                intent="media.rickmorty_character_search",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="media.rickmorty_character_search", args={"name": q})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar personagens (Rick and Morty).",
            )

        # pokemon
        m = re.search(r"\b(pokemon|pok[eé]mon)\b\s*[:\-]?\s*([\w\-]{1,40})\b", msg, flags=re.IGNORECASE)
        if m and (m.group(2) or "").strip():
            name_or_id = (m.group(2) or "").strip().lower()
            return Plan(
                intent="fun.pokemon_info",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="fun.pokemon_info", args={"name_or_id": name_or_id})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar informações do Pokémon.",
            )

        # letra de música
        m = re.search(r"\b(letra|lyrics)\b\s*[:\-]?\s*(.+)$", msg, flags=re.IGNORECASE)
        if m and (m.group(2) or "").strip():
            q = (m.group(2) or "").strip().strip('"\'')
            return Plan(
                intent="media.lyrics",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="media.lyrics", args={"query": q})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar a letra.",
            )

        return None


@dataclass(frozen=True)
class LanguageAndQaHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        msg = user_message.strip()

        m = re.search(r"\b(defina|definir|dicion[aá]rio|dictionary)\b\s+(.+)$", msg, flags=re.IGNORECASE)
        if m and (m.group(2) or "").strip():
            w = (m.group(2) or "").strip().strip('"\'')
            return Plan(
                intent="language.dictionary_define",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="language.dictionary_define", args={"word": w, "lang": "en"})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar a definição.",
            )

        m = re.search(r"\b(stack\s*overflow|stackoverflow|stack\s*exchange|stackexchange)\b\s*[:\-]?\s*(.+)$", msg, flags=re.IGNORECASE)
        if m and (m.group(2) or "").strip():
            q = (m.group(2) or "").strip().strip('"\'')
            return Plan(
                intent="qa.stackexchange_search",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="qa.stackexchange_search", args={"query": q, "site": "stackoverflow", "pagesize": 5})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar no Stack Overflow.",
            )

        return None


@dataclass(frozen=True)
class CodeSearchHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        msg = user_message.strip()
        m = re.search(r"\bgithub\b\s*[:\-]?\s*(.+)$", msg, flags=re.IGNORECASE)
        if m and (m.group(1) or "").strip():
            q = (m.group(1) or "").strip().strip('"\'')
            return Plan(
                intent="code.github_repo_search",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="code.github_repo_search", args={"query": q, "per_page": 5})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar repositórios no GitHub.",
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


@dataclass(frozen=True)
class FilesystemHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        msg = user_message.strip()
        if not _RE_FS_WORD.search(norm):
            return None

        path = _extract_path(msg) or "."

        # List directory
        if _RE_LIST_WORD.search(norm) and any(w in norm for w in ("listar", "lista", "conteudo", "conteúdo", "pastas", "arquivos", "dir", "folder")):
            return Plan(
                intent="fs.list_dir",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="fs.list_dir", args={"path": path})],
                risk=RiskLevel.LOW,
                final_response="Ok — vou listar o diretório.",
            )

        # Read file
        if _RE_READ_WORD.search(norm) and ("ler" in norm or "leia" in norm or "conteudo" in norm or "conteúdo" in norm):
            return Plan(
                intent="fs.read_text",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="fs.read_text", args={"path": path, "max_chars": 8000})],
                risk=RiskLevel.LOW,
                final_response="Ok — vou ler o arquivo (texto).",
            )

        return None


@dataclass(frozen=True)
class VSCodeConfigHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        msg = user_message.strip()
        if not (_RE_VSCODE_WORD.search(norm) or ".vscode" in norm or _RE_TASKS_WORD.search(norm) or _RE_SETTINGS_WORD.search(norm) or _RE_LAUNCH_WORD.search(norm)):
            return None

        # Open workspace
        if _RE_VSCODE_WORD.search(norm) and any(w in norm for w in ("abrir", "abra", "open")):
            return Plan(
                intent="vscode.open",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="vscode.open", args={"path": "."})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou abrir o workspace no VS Code.",
            )

        # Read tasks/settings/launch
        if _RE_TASKS_WORD.search(norm) and any(w in norm for w in ("ler", "mostre", "mostrar", "ver")):
            return Plan(
                intent="vscode.tasks_read",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="vscode.tasks_read", args={})],
                risk=RiskLevel.LOW,
                final_response="Ok — vou ler o tasks.json.",
            )

        if _RE_SETTINGS_WORD.search(norm) and any(w in norm for w in ("ler", "mostre", "mostrar", "ver")):
            return Plan(
                intent="vscode.settings_read",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="vscode.settings_read", args={})],
                risk=RiskLevel.LOW,
                final_response="Ok — vou ler o settings.json.",
            )

        if _RE_LAUNCH_WORD.search(norm) and any(w in norm for w in ("ler", "mostre", "mostrar", "ver")):
            return Plan(
                intent="vscode.launch_read",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="vscode.launch_read", args={})],
                risk=RiskLevel.LOW,
                final_response="Ok — vou ler o launch.json.",
            )

        return None


@dataclass(frozen=True)
class ScreenVisionHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        msg = user_message.strip()

        wants_monitor = bool(_RE_REWIND_WORD.search(norm) and _RE_SCREEN_WORD.search(norm))
        if wants_monitor:
            if _RE_STATUS_WORD.search(norm):
                return Plan(
                    intent="vision.rewind_status",
                    user_message=msg,
                    tool_calls=[ToolCall(tool_name="screen.rewind_status", args={})],
                    risk=RiskLevel.LOW,
                    final_response="Aqui está o status do monitoramento de tela (rewind).",
                )

            if _RE_STOP_WORD.search(norm):
                return Plan(
                    intent="vision.stop_rewind",
                    user_message=msg,
                    tool_calls=[ToolCall(tool_name="screen.rewind_stop", args={})],
                    risk=RiskLevel.HIGH,
                    final_response="Ok — vou parar o monitoramento contínuo da tela (requer aprovação).",
                )

            if _RE_START_WORD.search(norm):
                return Plan(
                    intent="vision.start_rewind",
                    user_message=msg,
                    tool_calls=[ToolCall(tool_name="screen.rewind_start", args={})],
                    risk=RiskLevel.HIGH,
                    final_response="Ok — vou iniciar o monitoramento contínuo da tela (requer aprovação).",
                )

        is_screenshot = bool(_RE_SCREENSHOT_WORD.search(norm) or ("print" in norm and _RE_SCREEN_WORD.search(norm)))
        if is_screenshot:
            wants_desktop = bool(_RE_DESKTOP_WORD.search(norm))
            wants_save = bool(_RE_SAVE_WORD.search(norm))
            args: dict[str, str] = {}
            if wants_desktop and wants_save:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                args["path"] = f"desktop:/screen_{ts}.png"
            return Plan(
                intent="vision.screenshot",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="screen.screenshot", args=args)],
                risk=RiskLevel.MEDIUM,
                final_response=(
                    "Tirei uma captura de tela e salvei na Área de Trabalho." if (wants_desktop and wants_save) else "Tirei uma captura de tela."
                ),
            )

        return None


@dataclass(frozen=True)
class WeatherHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        msg = user_message.strip()
        m = _RE_WEATHER.search(msg)
        if not m:
            return None
        city = (m.group(2) or "").strip().strip('"\'')
        if not city:
            return None
        return Plan(
            intent="data.weather",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="data.weather_open_meteo", args={"city": city, "lang": "pt"})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou consultar o clima atual (Open-Meteo).",
        )


@dataclass(frozen=True)
class CryptoPriceHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        msg = user_message.strip()
        if not (_RE_CRYPTO_PRICE_WORD.search(norm) and _RE_CRYPTO_ASSET.search(norm)):
            return None
        m = _RE_CRYPTO_ASSET.search(norm)
        asset = (m.group(1) if m else "bitcoin")
        return Plan(
            intent="finance.crypto_price",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="finance.crypto_price", args={"asset": asset, "vs": "brl,usd"})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou consultar o preço atual (CoinGecko).",
        )


@dataclass(frozen=True)
class WikipediaExplicitHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        msg = user_message.strip()
        m = _RE_WIKIPEDIA_EXPLICIT_2.search(msg)
        if m and (m.group(3) or "").strip():
            q = (m.group(3) or "").strip().strip("\"'")
            if q.lower().startswith("sobre "):
                q = q[6:].strip()
            if q:
                return Plan(
                    intent="knowledge.wikipedia_summary",
                    user_message=msg,
                    tool_calls=[ToolCall(tool_name="knowledge.wikipedia_summary", args={"title": q, "lang": "pt"})],
                    risk=RiskLevel.MEDIUM,
                    final_response="Ok — vou buscar um resumo na Wikipedia.",
                )

        m = _RE_WIKIPEDIA_EXPLICIT_1.search(msg)
        if m and (m.group(2) or "").strip():
            q = (m.group(2) or "").strip().strip("\"'")
            if q:
                return Plan(
                    intent="knowledge.wikipedia_summary",
                    user_message=msg,
                    tool_calls=[ToolCall(tool_name="knowledge.wikipedia_summary", args={"title": q, "lang": "pt"})],
                    risk=RiskLevel.MEDIUM,
                    final_response="Ok — vou buscar um resumo na Wikipedia.",
                )

        return None


@dataclass(frozen=True)
class GeoHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        msg = user_message.strip()

        m = _RE_ONDE_FICA.match(msg)
        if m and (m.group(1) or "").strip():
            q = (m.group(1) or "").strip().strip("\"'")
            if q:
                return Plan(
                    intent="geo.geocode",
                    user_message=msg,
                    tool_calls=[ToolCall(tool_name="geo.geocode", args={"query": q, "lang": "pt"})],
                    risk=RiskLevel.MEDIUM,
                    final_response="Ok — vou localizar no mapa (OpenStreetMap).",
                )

        m = _RE_GEOCODE.search(msg)
        if m and (m.group(2) or "").strip():
            q = (m.group(2) or "").strip().strip("\"'")
            if q:
                return Plan(
                    intent="geo.geocode",
                    user_message=msg,
                    tool_calls=[ToolCall(tool_name="geo.geocode", args={"query": q, "lang": "pt"})],
                    risk=RiskLevel.MEDIUM,
                    final_response="Ok — vou localizar as coordenadas (OpenStreetMap).",
                )

        if ((("endereco" in norm) or ("endereço" in norm)) and " de " in norm) or ("reverse" in norm):
            nums = re.findall(r"-?\d+(?:[\.,]\d+)?", msg)
            if len(nums) >= 2:
                try:
                    lat = float(nums[0].replace(",", "."))
                    lon = float(nums[1].replace(",", "."))
                except Exception:
                    lat = None
                    lon = None
                if lat is not None and lon is not None:
                    return Plan(
                        intent="geo.reverse_geocode",
                        user_message=msg,
                        tool_calls=[ToolCall(tool_name="geo.reverse_geocode", args={"lat": lat, "lon": lon, "lang": "pt"})],
                        risk=RiskLevel.MEDIUM,
                        final_response="Ok — vou buscar o endereço aproximado (OpenStreetMap).",
                    )

        m = _RE_ROUTE.search(msg)
        if m:
            origin = (m.group(3) or "").strip().strip("\"'")
            dest = (m.group(5) or "").strip().strip("\"'")
            if origin and dest:
                return Plan(
                    intent="geo.route_osrm",
                    user_message=msg,
                    tool_calls=[ToolCall(tool_name="geo.route_osrm", args={"from": origin, "to": dest, "profile": "driving", "lang": "pt"})],
                    risk=RiskLevel.MEDIUM,
                    final_response="Ok — vou traçar uma rota (OSRM + OpenStreetMap).",
                )

        return None


@dataclass(frozen=True)
class FxConvertHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        msg = user_message.strip()
        m = _RE_FX_CONVERT.search(msg)
        if not m:
            return None
        amount_s = (m.group(2) or "").strip().replace(",", ".")
        cur_from = (m.group(3) or "").strip().upper()
        cur_to = (m.group(4) or "").strip().upper()
        try:
            amount = float(amount_s)
        except Exception:
            return None
        return Plan(
            intent="finance.fx_convert",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="finance.fx_convert", args={"amount": amount, "from": cur_from, "to": cur_to})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou converter a moeda (Frankfurter/ECB).",
        )


@dataclass(frozen=True)
class CountryInfoHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        msg = user_message.strip()
        m = _RE_COUNTRY_INFO.search(msg)
        if not m or not (m.group(2) or "").strip():
            return None
        q = (m.group(2) or "").strip().strip("\"'")
        if not q:
            return None
        return Plan(
            intent="data.country_info",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="data.country_info", args={"query": q})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou buscar informações do país (RestCountries).",
        )


@dataclass(frozen=True)
class WorldTimeHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        msg = user_message.strip()
        m = _RE_WORLD_TIME.search(msg)
        if not m or not (m.group(2) or "").strip():
            return None
        tz = (m.group(2) or "").strip()
        if tz.lower() in {"brasilia", "brasil", "sao_paulo", "sao-paulo", "sao paulo"}:
            tz = "America/Sao_Paulo"
        return Plan(
            intent="time.world_time",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="time.world_time", args={"tz": tz})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou consultar a hora atual (WorldTimeAPI).",
        )


@dataclass(frozen=True)
class NewsHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        # Preserve legacy guard: don't treat Hacker News requests as GDELT.
        if "hacker news" in norm:
            return None
        msg = user_message.strip()
        m = _RE_NEWS.search(msg)
        if not m or not (m.group(2) or "").strip():
            return None
        q = (m.group(2) or "").strip().strip("\"'")
        if not q:
            return None
        return Plan(
            intent="news.gdelt_search",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="news.gdelt_search", args={"query": q, "max_results": 5})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou buscar notícias recentes (GDELT).",
        )


@dataclass(frozen=True)
class BooksHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        msg = user_message.strip()
        m = _RE_BOOK.search(msg)
        if not m or not (m.group(2) or "").strip():
            return None
        q = (m.group(2) or "").strip().strip("\"'")
        if not q:
            return None
        return Plan(
            intent="books.openlibrary_search",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="books.openlibrary_search", args={"query": q, "max_results": 5})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou buscar livros (OpenLibrary).",
        )


@dataclass(frozen=True)
class IbgeHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        msg = user_message.strip()

        # Estados / UFs
        if re.search(r"\bibge\b", norm) and re.search(r"\b(estados|ufs)\b", norm):
            return Plan(
                intent="br.ibge_states",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="br.ibge_states", args={})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou listar os estados (IBGE).",
            )

        # Municípios por UF
        m = re.search(r"\bibge\b\s+(?:municipios|munic[ií]pios)\b\s*[:\-]\s*([A-Za-z]{2})\b", msg, flags=re.IGNORECASE)
        if m and (m.group(1) or "").strip():
            uf = (m.group(1) or "").strip().upper()
            return Plan(
                intent="br.ibge_municipalities_by_uf",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="br.ibge_municipalities_by_uf", args={"uf": uf, "limit": 20})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou listar municípios por UF (IBGE).",
            )

        return None


def _strip_quotes(s: str) -> str:
    return str(s or "").strip().strip('"\'')


@dataclass(frozen=True)
class DiscordActionHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        msg = user_message.strip()

        # Abrir Discord
        if "discord" in norm and re.search(r"\b(abrir|abra|abre|open)\b", norm):
            return Plan(
                intent="os.open_app",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="os.open_app", args={"app": "discord"})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok, abri o Discord.",
            )

        # Fechar Discord
        if "discord" in norm and re.search(r"\b(fechar|feche|fecha|close|encerrar)\b", norm):
            in_background = bool(re.search(r"\b(segundo plano|background|bandeja|tray|minimizad[oa])\b", norm))
            return Plan(
                intent="os.close_app",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="os.close_app", args={"app": "discord", "visible_only": (not in_background)})],
                risk=RiskLevel.HIGH,
                final_response="Ok — vou fechar o Discord (requer aprovação).",
            )

        # Enviar mensagem no Discord (com ou sem menção explícita a Discord)
        m = re.search(
            r"\b(mandar|enviar)\b.*\b(mensagem|msg)\b.*\b(para|pra)\b\s*(?P<to>[^:]+?)\s*(?:\bno\b\s*discord|\bdiscord\b)?\s*[:\-]\s*(?P<text>.+)$",
            msg,
            flags=re.IGNORECASE,
        )
        if m:
            to = _strip_quotes(m.group("to") or "")
            text = (m.group("text") or "").strip()
            if to and text:
                return Plan(
                    intent="discord.send_message",
                    user_message=msg,
                    tool_calls=[
                        ToolCall(tool_name="os.open_app", args={"app": "discord"}),
                        ToolCall(tool_name="discord.send_message", args={"to": to, "message": text, "settle_ms": 900}),
                    ],
                    risk=RiskLevel.CRITICAL,
                    final_response="Ok — vou enviar a mensagem no Discord (requer aprovação).",
                )

        m = re.search(
            r"\bclique\b.*\bchat\b.*\bda\b\s*(?P<to>[^,.;:]+?)\s+e\s+\bmande\b\s+(?P<text>.+)$",
            msg,
            flags=re.IGNORECASE,
        )
        if m:
            to = _strip_quotes(m.group("to") or "")
            text = (m.group("text") or "").strip()
            text = re.sub(r"\b(pra|para)\s+(ela|ele|ele(a)?)\b\s*$", "", text, flags=re.IGNORECASE).strip()
            if re.fullmatch(r"(um\s+)?oi", (norm_text := re.sub(r"\s+", " ", _strip_quotes(text).lower())).strip()):
                text = "oi"
            if to and text:
                return Plan(
                    intent="discord.send_message",
                    user_message=msg,
                    tool_calls=[
                        ToolCall(tool_name="os.open_app", args={"app": "discord"}),
                        ToolCall(tool_name="discord.send_message", args={"to": to, "message": text, "settle_ms": 900}),
                    ],
                    risk=RiskLevel.CRITICAL,
                    final_response="Ok — vou abrir o chat e enviar a mensagem no Discord (requer aprovação).",
                )

        return None


@dataclass(frozen=True)
class JgraspHelloWorldHandler:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        msg = user_message.strip()
        if "jgrasp" not in norm:
            return None
        if not re.search(r"\b(criar|crie|cria|fazer|faca|faça|gerar|gere|montar)\b", norm):
            return None
        if not (re.search(r"\b(programa|projeto)\b", norm) and re.search(r"\b(simples|hello\s*world|ol[aá]\s*,?\s*mundo)\b", norm)):
            return None

        wants_desktop = bool(re.search(r"\b([aá]rea de trabalho|area de trabalho|desktop)\b", norm))
        path = "scratch/HelloWorld.java"
        class_name = "HelloWorld"
        if wants_desktop:
            path = "desktop:/MeuProjeto/MeuProjeto.java"
            class_name = "MeuProjeto"

        return Plan(
            intent="jgrasp.create_java_program",
            user_message=msg,
            tool_calls=[
                ToolCall(tool_name="os.open_app", args={"app": "jgrasp"}),
                ToolCall(
                    tool_name="jgrasp.create_java_program",
                    args={
                        "path": path,
                        "class_name": class_name,
                        "message": "Olá, mundo!",
                        "open_in_jgrasp": True,
                        "settle_ms": 900,
                    },
                ),
            ],
            risk=RiskLevel.HIGH,
            final_response="Ok — vou criar um programa Java simples no jGRASP (requer aprovação).",
        )


@dataclass(frozen=True)
class HolidaysHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        msg = user_message.strip()
        m = _RE_HOLIDAYS.search(msg)
        if not m:
            return None
        try:
            year = int(m.group(1) or 0)
        except Exception:
            return None
        cc = (m.group(2) or "").strip().upper()
        if not (year and cc):
            return None
        return Plan(
            intent="calendar.holidays",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="calendar.holidays", args={"year": year, "country_code": cc})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou listar feriados públicos (Nager.Date).",
        )


@dataclass(frozen=True)
class CrossrefHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        msg = user_message.strip()
        m = _RE_CROSSREF.search(msg)
        if not m or not (m.group(2) or "").strip():
            return None
        q = (m.group(2) or "").strip().strip("\"'")
        if not q:
            return None
        return Plan(
            intent="papers.crossref_search",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="papers.crossref_search", args={"query": q, "rows": 5})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou buscar referências/DOIs (Crossref).",
        )


@dataclass(frozen=True)
class CoreHelpHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        if not re.fullmatch(r"\b(ajuda|help|comandos)\b", norm):
            return None
        msg = user_message.strip()
        return Plan(
            intent="core.help",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="core.help", args={})],
            risk=RiskLevel.LOW,
            final_response="Ok — posso ajudar. Que tipo de tarefa você quer executar?",
        )


@dataclass(frozen=True)
class ScaffoldProjectHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        m = re.search(r"\b(crie|criar|gera|gerar)\b.*\bprojeto\b.*\bpython\b", norm)
        if not m:
            return None
        mm = re.search(r"\bchamad[oa]\b\s+([\w\-]{1,60})\b", norm)
        project_name = (mm.group(1) if mm else "MeuProjeto").strip()
        return Plan(
            intent="dev.scaffold_project",
            user_message=user_message.strip(),
            tool_calls=[ToolCall(tool_name="dev.scaffold_project", args={"language": "python", "name": project_name})],
            risk=RiskLevel.HIGH,
            final_response=f"Ok — vou criar um projeto Python chamado {project_name}.",
        )


@dataclass(frozen=True)
class TrexHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        if not re.search(r"\b(t\s*[- ]?rex|trex)\b", norm):
            return None
        if not re.search(r"\b(jogo|joguinho|autoplay|joga|jogar)\b", norm):
            return None
        msg = user_message.strip()
        return Plan(
            intent="game.trex_autoplay",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="game.trex_autoplay", args={})],
            risk=RiskLevel.HIGH,
            final_response="Ok — vou jogar o T-Rex automaticamente.",
        )


@dataclass(frozen=True)
class PdfWordAutofillHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        if not re.search(r"\bpdf\b", norm):
            return None
        if not re.search(r"\b(atividades|atividade|exerc[ií]cios|fa[cç]a|fazer)\b", norm):
            return None

        msg = user_message.strip()
        solve_with_llm = bool(re.search(r"\b(responda|responder|respostas|responda\s+as\s+quest[oõ]es|responda\s+as\s+questões)\b", norm))

        pdf_title_contains = None
        m = re.search(r"\bpdf\b\s*\"([^\"]{1,200}\.pdf)\"", msg, flags=re.IGNORECASE)
        if m:
            pdf_title_contains = (m.group(1) or "").strip()
        else:
            m = re.search(r"\bPDF\b\s*\"([^\"]{1,200}\.pdf)\"", msg)
            if m:
                pdf_title_contains = (m.group(1) or "").strip()

        output_mode = "word"
        out_path = None

        m = re.search(r"\bdocx\b\s*\"([^\"]{1,200}\.docx)\"", msg, flags=re.IGNORECASE)
        if m and (m.group(1) or "").strip():
            output_mode = "docx"
            out_path = f"data/tmp/{(m.group(1) or '').strip()}"

        if re.search(r"\b(gerar|gere)\b", norm) and re.search(r"\bdocxs?\b", norm) and out_path is None:
            output_mode = "docx"
            out_path = "data/tmp/atividades.docx"

        if re.search(r"\b(gerar|gere)\b", norm) and re.search(r"\bpdf\b", norm) and out_path is None:
            output_mode = "pdf"
            out_path = "data/tmp/atividades.pdf"

        if re.search(r"\b(gerar|gere)\b", norm) and re.search(r"\bdocx\b", norm) and out_path is None:
            output_mode = "docx"
            out_path = "data/tmp/atividades.docx"

        if re.search(r"\b(área\s+de\s+trabalho|area\s+de\s+trabalho|desktop)\b", norm) and output_mode == "docx":
            out_path = "desktop:/atividades.docx"

        args: dict[str, object] = {
            "solve_with_llm": solve_with_llm,
            "output_mode": output_mode,
        }
        if pdf_title_contains:
            args["pdf_title_contains"] = pdf_title_contains
        else:
            args["assume_focused_pdf"] = True

        if out_path is not None:
            args["out_path"] = out_path

        return Plan(
            intent="edu.pdf_word_autofill",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="edu.pdf_word_autofill", args=args)],
            risk=RiskLevel.HIGH,
            final_response="Ok — vou preencher as atividades do PDF no Word.",
        )


@dataclass(frozen=True)
class CompileHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        if not re.search(r"\b(compila|compilar|compile|build)\b", norm):
            return None
        msg = user_message.strip()
        return Plan(
            intent="dev.exec",
            user_message=msg,
            tool_calls=[
                ToolCall(tool_name="dev.exec", args={"command": "python -m compileall -q omniscia"}),
                ToolCall(tool_name="dev.exec", args={"command": "python -m pytest -q"}),
            ],
            risk=RiskLevel.HIGH,
            final_response="Ok — vou compilar e rodar os testes.",
        )


@dataclass(frozen=True)
class GameAutoplayHandlers:
    def try_handle(self, *, user_message: str, norm: str, context_messages: list[dict[str, str]] | None) -> Plan | None:
        if not re.search(r"\b(jogue|jogar|jogo|game|play)\b", norm):
            return None
        if re.search(r"\b(t\s*[- ]?rex|trex)\b", norm):
            return None
        if re.search(r"\b(online|competitiv|ranked|pvp|multiplayer)\b", norm):
            return Plan(
                intent="chat",
                user_message=user_message.strip(),
                tool_calls=[],
                risk=RiskLevel.LOW,
                final_response="Não posso automatizar jogos online competitivos. Posso sugerir treinos offline ou dicas gerais.",
            )
        msg = user_message.strip()
        return Plan(
            intent="game.autoplay",
            user_message=msg,
            tool_calls=[
                ToolCall(tool_name="game.calibrate_runner_from_mouse", args={}),
                ToolCall(tool_name="game.autoplay", args={}),
            ],
            risk=RiskLevel.HIGH,
            final_response="Ok — vou calibrar e jogar automaticamente.",
        )


_HANDLERS: tuple[HeuristicHandler, ...] = (
    NumericOnlyHandler(),
    SessionTogglesHandler(),
    CoreHelpHandlers(),
    ProfilePrefsHandler(),
    StatusHandlers(),
    CoreOpsHandlers(),
    MemoryCompactHandler(),
    ScaffoldProjectHandlers(),
    PdfWordAutofillHandlers(),
    CompileHandlers(),
    TrexHandlers(),
    GameAutoplayHandlers(),
    PublicApisHandlers(),
    MorePublicApisHandlers(),
    CodeSearchHandlers(),
    LanguageAndQaHandlers(),
    FunAndMediaHandlers(),
    CryptoKnowledgeHandlers(),
    FilesystemHandlers(),
    VSCodeConfigHandlers(),
    ScreenVisionHandlers(),
    WeatherHandlers(),
    CryptoPriceHandlers(),
    WikipediaExplicitHandlers(),
    GeoHandlers(),
    FxConvertHandlers(),
    CountryInfoHandlers(),
    WorldTimeHandlers(),
    NewsHandlers(),
    BooksHandlers(),
    IbgeHandlers(),
    DiscordActionHandlers(),
    JgraspHelloWorldHandler(),
    HolidaysHandlers(),
    CrossrefHandlers(),
    FearGreedIndexHandler(),
    ISSPositionHandler(),
    EarthquakeUSGSHandler(),
    CovidStatsHandler(),
    ServiceStatusHandler(),
    ArticSearchHandler(),
    ChessComHandler(),
    OpenBreweryDBHandler(),
    DeckOfCardsHandler(),
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
        except Exception as exc:  # noqa: BLE001
            # Heurística nunca deve derrubar o router; fallback para o legado.
            # Mas não pode falhar silenciosamente: precisamos de visibilidade.
            handler_name = getattr(h, "__class__", type(h)).__name__
            logger.warning("Heuristic handler %s falhou: %s", handler_name, exc, exc_info=True)
            continue
        if plan is not None:
            return plan
    return None
