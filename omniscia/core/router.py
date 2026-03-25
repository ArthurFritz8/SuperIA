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
import os
import re
import unicodedata
import asyncio
from datetime import datetime
from collections import OrderedDict
from typing import Any
from urllib.parse import quote_plus

from omniscia.core.config import Settings
from omniscia.core.heuristic_handlers import run_heuristic_handlers
from omniscia.core.router_cache import build_router_cache_from_env, make_cache_key_namespace
from omniscia.core.router_prompt_data import load_schema_hints, load_static_tools_block
from omniscia.core.tool_rag import build_shortlister_from_env
from omniscia.core.tools import ToolRegistry
from omniscia.core.types import Plan, RiskLevel, ToolCall

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    try:
        v = int(str(os.getenv(name, str(default))).strip())
        return v if v > 0 else default
    except Exception:
        return default


class _LRUCache:
    def __init__(self, max_items: int) -> None:
        self.max_items = max(0, int(max_items or 0))
        self._data: "OrderedDict[str, Plan]" = OrderedDict()

    def get(self, key: str) -> Plan | None:
        if not self.max_items:
            return None
        try:
            val = self._data.pop(key)
        except KeyError:
            return None
        self._data[key] = val
        # Retorna cópia para evitar mutação acidental
        try:
            return val.model_copy(deep=True)
        except Exception:
            return val

    def put(self, key: str, value: Plan) -> None:
        if not self.max_items:
            return
        if key in self._data:
            try:
                self._data.pop(key)
            except KeyError:
                pass
        self._data[key] = value
        while len(self._data) > self.max_items:
            self._data.popitem(last=False)


_HEURISTIC_CACHE = _LRUCache(_env_int("OMNI_HEURISTIC_ROUTE_CACHE", 512))
_LLM_ROUTE_CACHE = _LRUCache(_env_int("OMNI_LLM_ROUTE_CACHE", 128))

# Opt-in caches / indexes
_SQLITE_CACHE = build_router_cache_from_env()
_TOOL_SHORTLISTER = build_shortlister_from_env()


def _registry_fingerprint(registry: ToolRegistry | None) -> str:
    if registry is None:
        return "-"
    try:
        names = sorted([t.name for t in registry.list() if getattr(t, "name", None)])
        if not names:
            return "0"
        # fingerprint simples e barato: tamanho + bordas
        return f"{len(names)}:{names[0]}:{names[-1]}"
    except Exception:
        return "?"


# Regex precompiladas (hot-path)
# Motivação: evitar recompilar dezenas de padrões a cada mensagem.
_RE_GUI_EXPLICIT = re.compile(
    r"\b(clica|clicar|clique|mouse|teclado|digita|digitar|digite|aperta|apertar|pressione|pressionar)\b"
)
_RE_SCREEN_EXPLICIT = re.compile(
    r"\b(screenshot|print\s*screen|printscreen|captura\s+de\s+tela|ocr|ler\s+texto|leia\s+o\s+texto)\b"
)
_RE_IMPERATIVE = re.compile(r"\b(olha|olhe|veja|ver|verifique|analise|analisa|mostra|mostre|leia)\b")
_RE_SCREEN_WORD = re.compile(r"\b(tela|screen)\b")
_RE_DEV_EXPLICIT = re.compile(r"\b(rode|rodar|executa|execute|comando|terminal|cmd|powershell)\b")
_RE_WEB_EXPLICIT = re.compile(
    r"\b(pesquise|pesquisa|procure|buscar|busque|consulta|consulte|no\s+google|na\s+web|na\s+internet|wikipedia|wiki|cotacao|cota[cç]ao|pre[cç]o|grafico|gr[aá]fico|chart)\b"
)
_RE_GREETING_FULL = re.compile(
    r"(oi|ola|opa|eai|e\s*ai|salve|bom\s+dia|boa\s+tarde|boa\s+noite)(\s+tudo\s+bem)?[!.?]*"
)
_RE_OS_VERBS = re.compile(r"\b(abrir|abra|abre|open|fechar|feche|fecha|close)\b")
_RE_URL = re.compile(r"\bhttps?://\S+\b")
_RE_WWW = re.compile(r"\bwww\.[^\s]+\b")
_RE_DISCORD_MSG_HINT = re.compile(r"\b(mensagem|msg|chat)\b")
_RE_JGRASP_WORD = re.compile(r"\bjgrasp\b")
_RE_BUILD_VERB = re.compile(r"\b(crie|criar|escreva|escrever|gere|gerar|fa[cç]a|faca|implemente|implementar|compile|compilar)\b")
_PROGRAMMING_HINT = re.compile(r"\b(jgrasp|java|python|javascript|typescript|c\+\+|c#|csharp|html|css)\b")


_DETERMINISTIC_INTENTS: set[str] = {
    # OS openers
    "os.open_url",
    "os.open_explorer",
    "os.open_app",
    "os.close_app",
    "os.scan_apps",
    "os.generate_open_apps",
    "os.list_processes",
    "os.list_installed_apps",
    "os.mkdir",
    # Filesystem routines
    "fs.list_dir",
    "fs.read_text",
    "fs.delete",
    "fs.mkdir",
    "fs.copy",
    "fs.move",
    # Vision basics
    "screen.screenshot",
    "screen.ocr",
    # Router intents for vision
    "vision.screenshot",
    "vision.ocr",
    # GUI explicit coordinates
    "gui.get_mouse",
    "gui.move_mouse",
    "gui.click",
    "gui.click_box_center",
    "gui.type_text",
    "gui.press_key",
    # Games
    "game.trex_autoplay",
    "game.autoplay",
    "game.list_profiles",
    "game.save_profile",
    "game.calibrate_runner_from_mouse",
    # Education
    "edu.pdf_word_autofill",
    # Web read-only
    "web.get_page_text",
    "web.research",
    # Public API integrations (read-only)
    "data.weather",
    "finance.crypto_price",
    "finance.crypto_market_chart",
    "knowledge.wikipedia_summary",
    "papers.arxiv_search",
    "web.search",
    "geo.geocode",
    "geo.reverse_geocode",
    "geo.route_osrm",
    "finance.fx_convert",
    "data.country_info",
    "time.world_time",
    "news.gdelt_search",
    "books.openlibrary_search",
    "calendar.holidays",
    "papers.crossref_search",
    "finance.fear_greed_index",
    "science.earthquake_usgs",
    "space.iss_position",
    "health.covid_stats",
    "knowledge.openalex_works_search",
    "knowledge.wikidata_search",
    "knowledge.wikidata_entity",
    "data.worldbank_indicator",
    "news.hackernews_front_page",
    "code.github_repo_search",
    "qa.stackexchange_search",
    "language.dictionary_define",
    "media.lyrics",
    "fun.joke",
    "fun.trivia",
    "fun.pokemon_info",
    "net.ip_info",
    "people.random_user",
    "fun.cat_fact",
    "utils.qr_code_url",
    "sec.osv_vuln",
    "sec.osv_query",
    "pkg.pypi_project",
    "pkg.npm_package",
    "pkg.cratesio_crate",
    "net.dns_google_resolve",
    "status.github",
    "net.rdap_domain",
    "net.rdap_ip",
    "net.bgpview_ip",
    "net.bgpview_asn",
    "sec.crtsh_search",
    "sec.cisa_kev_search",
    "status.cloudflare",
    "status.discord",
    "net.ripestat_ip",
    "net.ripestat_asn",
    "net.peeringdb_asn",
    "sec.urlhaus_url",
    "sec.urlhaus_host",
    "sec.threatfox_ioc_search",
    "status.npm",
    "status.openai",
    "status.docker",
    "sec.feodotracker_ip_blocklist",
    "sec.hashlookup",
    "status.atlassian",
    "status.zoom",
    "status.gitlab",
    "space.spacex_latest_launch",
    "archive.archiveorg_search",
    "media.tvmaze_search",
    "food.meal_search",
    "edu.universities_search",
    "people.agify_name",
    "people.genderize_name",
    "people.nationalize_name",
    "fun.dog_image",
    "anime.jikan_search",
    "art.met_search",
    "art.met_object",
    "art.artic_search",
    "chess.chesscom_player",
    "chess.chesscom_stats",
    "chess.chesscom_daily_puzzle",
    "drink.openbrewerydb_search",
    "fun.deck_draw",
    "fun.xkcd_latest",
    "fun.xkcd_comic",
    "music.itunes_search",
    "books.gutendex_search",
    "data.openfoodfacts_search",
    "pkg.npm_downloads_last_week",
    "books.googlebooks_search",
    "fun.quote_random",
    "fun.advice",
    "fun.bored_activity",
    "fun.fox_image",
    "fun.duck_image",
    "language.datamuse_related_words",
    "cards.scryfall_search",
    "cards.scryfall_random",
    "media.rickmorty_character_search",
    "time.sunrise_sunset",
    "fun.dadjoke",
    "fun.jokeapi",
    "br.ibge_states",
    "br.ibge_municipalities_by_uf",
    "br.viacep_lookup",
    "win.focus_window",
    "win.list_windows",
    "win.foreground_window",
    "discord.send_message",
    "jgrasp.create_java_program",
    "jgrasp.write_code",
    # DevAgent (explicit)
    "dev.exec",
    "dev.run_python",
    "dev.autofix_python_file",
    "dev.autofix_cmd",
    "dev.scaffold_project",
    # Session toggles
    "core.omega_on",
    "core.omega_off",
    "core.voice_on",
    "core.voice_off",
    "core.autonomy_on",
    "core.autonomy_off",
    "core.doctor",
    "core.approvals_list",
    "core.approvals_revoke",
    "core.approvals_reset",
    "core.policy_show",
    "core.policy_write",
    "core.snapshot_create",
    "core.snapshot_list",
    "core.snapshot_restore",
    "core.memory_compact",
    # Perfil persistente (memória de longo prazo)
    "memory.profile_get",
    "memory.profile_update",
    "memory.profile_reset",
    "core.help",

    # VS Code (CLI + .vscode/*)
    "vscode.open",
    "vscode.open_file",
    "vscode.list_extensions",
    "vscode.install_extension",
    "vscode.uninstall_extension",
    "vscode.settings_read",
    "vscode.settings_get",
    "vscode.settings_update",
    "vscode.extensions_read",
    "vscode.extensions_update",
    "vscode.tasks_read",
    "vscode.tasks_update",
    "vscode.launch_read",
    "vscode.launch_update",
}


def _normalize(text: str) -> str:
    """Normaliza texto para matching heurístico.

    Motivação:
    - Acentos e encoding variam entre terminais (Windows, bash, PowerShell).
    - Para heurísticas simples, a normalização reduz falsos negativos.

    Estratégia:
    - lowercase
    - remove acentos via NFKD
    """

    t = (text or "").strip().lower()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return t


def _looks_like_chat_message(norm: str) -> bool:
    """Retorna True quando a mensagem parece conversa (sem pedido explícito de tools).

    Objetivo: reduzir latência e uso de recursos evitando uma chamada extra ao LLM
    só para roteamento em mensagens claramente conversacionais.

    Regras:
    - Se houver pedido explícito de web/GUI/dev, NÃO é chat.
    - Caso contrário, trata como chat (conservador para evitar tool acidental).
    """

    n = (norm or "").strip()
    if not n:
        return True

    # Pedidos explícitos de GUI (cliques/teclado).
    if _RE_GUI_EXPLICIT.search(n):
        return False

    # Pedidos explícitos de screenshot/OCR.
    if _RE_SCREEN_EXPLICIT.search(n):
        return False

    # Imperativo + tela/screen (apenas quando explícito).
    has_imperative = bool(_RE_IMPERATIVE.search(n))
    has_screen_word = bool(_RE_SCREEN_WORD.search(n))
    if has_imperative and has_screen_word:
        return False

    # Pedidos explícitos de execução/terminal.
    if _RE_DEV_EXPLICIT.search(n):
        return False

    # Pedidos explícitos de programação/código (ex.: jGRASP/Java) não são chat.
    has_programming_hint = bool(_RE_PROGRAMMING_HINT.search(n))
    has_build_verb = bool(_RE_BUILD_VERB.search(n))
    if has_programming_hint and has_build_verb:
        return False

    # Pedidos explícitos de web/pesquisa/APIs.
    if _RE_WEB_EXPLICIT.search(n):
        return False

    return True


def _is_greeting(norm: str) -> bool:
    """Detecta cumprimentos curtos (para resposta instantânea e determinística).

    Importante:
    - `norm` deve vir de `_normalize()` (sem acentos, lowercase).
    - Só casa mensagens curtas; se houver mais conteúdo, deixa seguir o fluxo normal.
    """

    n = (norm or "").strip()
    if not n:
        return False

    # Exemplos: "oi", "ola", "olá", "bom dia", "boa tarde", "boa noite",
    # "oi tudo bem", "ola!"
    return bool(_RE_GREETING_FULL.fullmatch(n))


def route(settings: Settings, user_message: str) -> Plan:
    # Exit must be handled deterministically before any LLM routing.
    # Otherwise the LLM may hallucinate a destructive action (e.g., shutdown).
    if _normalize(user_message) in {"sair", "exit", "quit"}:
        msg = user_message.strip()
        return Plan(intent="exit", user_message=msg, final_response="Encerrando.")

    # Cumprimentos: resposta instantânea (sem router LLM e sem tools).
    norm = _normalize(user_message)
    if _is_greeting(norm):
        return Plan(
            intent="chat",
            user_message=user_message.strip(),
            tool_calls=[],
            risk=RiskLevel.LOW,
            final_response="Oi! Em que posso te ajudar?",
        )

    # Prefer deterministic heuristics whenever they match.
    # This improves UX (no latency/quota) and avoids LLM hallucinations.
    cache_key = ""
    try:
        cache_key = "h1:" + _normalize(user_message)
    except Exception:
        cache_key = ""
    heuristic = _HEURISTIC_CACHE.get(cache_key) if cache_key else None
    if heuristic is None:
        heuristic = _route_heuristic(user_message, context_messages=None)
        if cache_key:
            _HEURISTIC_CACHE.put(cache_key, heuristic)
    if heuristic.intent in _DETERMINISTIC_INTENTS:
        return heuristic

    # Fast-path: em mensagens claramente conversacionais, não chama o router LLM.
    # Isso evita 2 chamadas por turno (route_llm + chat_reply) e melhora performance.
    if (
        heuristic.intent == "chat"
        and not heuristic.tool_calls
        and not (heuristic.final_response or "").strip()
        and _looks_like_chat_message(_normalize(user_message))
    ):
        return Plan(intent="chat", user_message=user_message.strip(), tool_calls=[], risk=RiskLevel.LOW)

    if settings.router_mode == "llm":
        plan = route_llm(settings, user_message, heuristic_fallback=heuristic)
        if plan is not None:
            return plan

    return heuristic


def route_with_registry(
    settings: Settings,
    user_message: str,
    *,
    registry: ToolRegistry,
    context_messages: list[dict[str, str]] | None = None,
    metrics: object | None = None,
    runlog: object | None = None,
    run: object | None = None,
) -> Plan:
    """Como `route()`, mas com conhecimento das tools registradas.

    Benefícios:
    - O router LLM só vê tools realmente disponíveis (melhor qualidade/menos falhas).
    - Podemos falhar cedo quando uma heuristic seleciona tool ausente (deps opcionais).

    Observação:
    - Mantemos `route()` intacta para compatibilidade em testes/uso externo.
    """

    # Exit must be handled deterministically before any LLM routing.
    if _normalize(user_message) in {"sair", "exit", "quit"}:
        msg = user_message.strip()
        return Plan(intent="exit", user_message=msg, final_response="Encerrando.")

    # Cumprimentos: resposta instantânea (sem router LLM e sem tools).
    norm = _normalize(user_message)
    if _is_greeting(norm):
        return Plan(
            intent="chat",
            user_message=user_message.strip(),
            tool_calls=[],
            risk=RiskLevel.LOW,
            final_response="Oi! Em que posso te ajudar?",
        )

    # Heurística pode ser cacheada apenas quando NÃO há contexto.
    heuristic: Plan
    t_route = None
    try:
        if metrics is not None:
            t_route = metrics.timer()
    except Exception:
        t_route = None
    if not context_messages:
        cache_key = "h1:" + _normalize(user_message)
        cached = _HEURISTIC_CACHE.get(cache_key)
        if cached is not None:
            heuristic = cached
            try:
                if metrics is not None:
                    metrics.inc("router.heuristic.cache_hit")
            except Exception:
                pass
        else:
            heuristic = _route_heuristic(user_message, context_messages=context_messages)
            _HEURISTIC_CACHE.put(cache_key, heuristic)
            try:
                if metrics is not None:
                    metrics.inc("router.heuristic.cache_miss")
            except Exception:
                pass
    else:
        heuristic = _route_heuristic(user_message, context_messages=context_messages)

    try:
        if metrics is not None and t_route is not None:
            metrics.observe_ms("router.heuristic.ms", t_route)
    except Exception:
        pass

    # Se a heuristic escolheu tools que não existem neste runtime, devolvemos orientação.
    # (isso acontece quando dependências opcionais não foram instaladas)
    if heuristic.tool_calls:
        missing: list[str] = []
        for c in heuristic.tool_calls:
            try:
                registry.get((c.tool_name or "").strip())
            except Exception:
                missing.append((c.tool_name or "").strip() or "(vazio)")
        if missing:
            return Plan(
                intent="chat",
                user_message=user_message.strip(),
                tool_calls=[],
                risk=RiskLevel.LOW,
                final_response=(
                    "Essa automação depende de tools que não estão disponíveis nesta instalação: "
                    + ", ".join(sorted(set(missing)))
                    + ".\n"
                    + "Rode: omniscia doctor\n"
                    + "e instale os extras sugeridos (ex.: pip install -e .[all])."
                ),
            )

    if heuristic.intent in _DETERMINISTIC_INTENTS:
        return heuristic

    # Mesmo fast-path da versão sem registry.
    if (
        heuristic.intent == "chat"
        and not heuristic.tool_calls
        and not (heuristic.final_response or "").strip()
        and _looks_like_chat_message(_normalize(user_message))
    ):
        return Plan(intent="chat", user_message=user_message.strip(), tool_calls=[], risk=RiskLevel.LOW)

    if settings.router_mode == "llm":
        plan = route_llm(
            settings,
            user_message,
            heuristic_fallback=heuristic,
            registry=registry,
            context_messages=context_messages,
            metrics=metrics,
            runlog=runlog,
            run=run,
        )
        if plan is not None:
            return plan

    return heuristic


async def route_with_registry_async(
    settings: Settings,
    user_message: str,
    *,
    registry: ToolRegistry,
    context_messages: list[dict[str, str]] | None = None,
    metrics: object | None = None,
    runlog: object | None = None,
    run: object | None = None,
) -> Plan:
    """Wrapper async (opt-in) para `route_with_registry` via thread."""

    return await asyncio.to_thread(
        route_with_registry,
        settings,
        user_message,
        registry=registry,
        context_messages=context_messages,
        metrics=metrics,
        runlog=runlog,
        run=run,
    )


def route_llm(
    settings: Settings,
    user_message: str,
    *,
    context_messages: list[dict[str, str]] | None = None,
    heuristic_fallback: Plan | None = None,
    registry: ToolRegistry | None = None,
    metrics: object | None = None,
    runlog: object | None = None,
    run: object | None = None,
) -> Plan | None:
    """Roteia via LLM (quando configurado), opcionalmente com contexto adicional.

    Uso:
    - `route()` chama isso para o primeiro plano em modo llm.
    - O loop ReAct pode chamar isso novamente após tool outputs, passando `context_messages`.

    Observação:
    - `context_messages` deve conter apenas roles "user"/"assistant".
    - Guardrails de segurança são aplicados aqui.
    """

    # Cache só quando NÃO há contexto adicional (rota inicial, mais comum).
    cache_key = ""
    try:
        if not context_messages:
            provider = str(getattr(settings, "llm_provider", "") or "").strip().lower()
            model = str(getattr(settings, "llm_model", "") or "").strip()
            base_url = str(getattr(settings, "llm_base_url", "") or "").strip()
            ns = make_cache_key_namespace(
                provider=provider,
                model=model,
                base_url=base_url,
                registry_fingerprint=_registry_fingerprint(registry),
            )
            cache_key = "l1:" + ns + "|" + _normalize(user_message)
    except Exception:
        cache_key = ""

    if cache_key:
        # 1) Cache persistente (se habilitado)
        if _SQLITE_CACHE is not None:
            # Best-effort: evita crescimento infinito do SQLite.
            try:
                keep_last_n = int(os.getenv("OMNI_ROUTER_SQLITE_CACHE_KEEP_LAST_N", "5000") or "5000")
                _SQLITE_CACHE.maybe_maintain(keep_last_n=keep_last_n)
            except Exception:
                pass
            cached_p = _SQLITE_CACHE.get(cache_key)
            if cached_p is not None:
                try:
                    if metrics is not None:
                        metrics.inc("router.llm.sqlite_hit")
                except Exception:
                    pass
                return cached_p

        # 2) Cache em memória
        cached = _LLM_ROUTE_CACHE.get(cache_key)
        if cached is not None:
            try:
                if metrics is not None:
                    metrics.inc("router.llm.mem_hit")
            except Exception:
                pass
            return cached

    t_llm = None
    try:
        if metrics is not None:
            t_llm = metrics.timer()
    except Exception:
        t_llm = None

    llm_kwargs: dict[str, Any] = {}
    if registry is not None:
        llm_kwargs["registry"] = registry

    plan = _route_with_llm_messages(
        settings,
        (context_messages or []) + [{"role": "user", "content": str(user_message or "").strip()}],
        **llm_kwargs,
    )
    try:
        if metrics is not None and t_llm is not None:
            metrics.observe_ms("router.llm.ms", t_llm)
            metrics.inc("router.llm.calls")
    except Exception:
        pass
    if plan is None:
        return None

    if runlog is not None and run is not None:
        try:
            runlog.append(
                run,
                "router_decision",
                {
                    "mode": "llm",
                    "intent": plan.intent,
                    "risk": str(plan.risk),
                    "tool_calls": [c.model_dump() for c in (plan.tool_calls or [])],
                    "cached": False,
                },
            )
        except Exception:
            pass

    if cache_key:
        _LLM_ROUTE_CACHE.put(cache_key, plan)
        if _SQLITE_CACHE is not None:
            _SQLITE_CACHE.put(cache_key, plan)

    norm = _normalize(user_message)

    def _asked_for_screen_or_gui(n: str) -> bool:
        # IMPORTANTE: não basta mencionar "tela".
        # Ex.: "na minha tela apareceu..." NÃO é pedido pra usar OCR/screenshot.
        # Só libera tools quando houver pedido explícito (imperativo) ou ação (clicar/digitar).

        # Pedidos explícitos de clique/teclado.
        if re.search(r"\b(pule|pular|jogue|jogar)\b", n) or _RE_GUI_EXPLICIT.search(n):
            return True

        # Pedidos explícitos de screenshot/OCR.
        if _RE_SCREEN_EXPLICIT.search(n):
            return True

        # Imperativo + tela/screen.
        has_imperative = bool(_RE_IMPERATIVE.search(n))
        has_screen_word = bool(_RE_SCREEN_WORD.search(n))
        return has_imperative and has_screen_word

    def _asked_for_dev_exec(n: str) -> bool:
        return bool(re.search(r"\bpython\b", n) or _RE_DEV_EXPLICIT.search(n))

    def _asked_for_os_action(n: str) -> bool:
        # Só liberamos ações no SO quando o usuário pedir explicitamente.
        # Exemplos: "abre o youtube", "abra o chrome", "feche o discord", ou uma URL explícita.
        if _RE_OS_VERBS.search(n):
            return True
        if _RE_URL.search(n):
            return True
        if _RE_WWW.search(n):
            return True
        return False

    def _asked_for_web_or_data(n: str) -> bool:
        # Só permitimos web/public APIs quando o usuário pedir explicitamente.
        # Isso evita buscas automáticas que geram captcha/blocks e melhora a UX.
        return bool(_RE_WEB_EXPLICIT.search(n) or re.search(r"\b(verifique|veja)\b", n))

    asked_screen_or_gui = _asked_for_screen_or_gui(norm)
    asked_dev = _asked_for_dev_exec(norm)
    asked_web = _asked_for_web_or_data(norm)
    asked_os = _asked_for_os_action(norm)
    asked_jgrasp_task = bool(_RE_JGRASP_WORD.search(norm) and _RE_BUILD_VERB.search(norm))

    def _has_forbidden_tools(p: Plan) -> bool:
        for c in p.tool_calls:
            name = (c.tool_name or "").strip()
            if name.startswith(("screen.", "gui.")) or name in {"win.focus_window"}:
                if not asked_screen_or_gui:
                    return True

            # OS side-effects (abrir/fechar apps/URLs) só quando solicitado.
            if name in {"os.open_url", "os.open_app", "os.open_explorer", "os.close_app"} and not asked_os:
                # Exceção segura: quando o usuário pediu uma tarefa no jGRASP, abrir o jGRASP é implícito.
                if name == "os.open_app" and asked_jgrasp_task:
                    app = str((c.args or {}).get("app") or "").strip().lower()
                    if app in {"jgrasp", "j-grasp"}:
                        continue
                return True

            if name.startswith("dev.") and not asked_dev:
                return True
            if name.startswith("web.") and not asked_web:
                return True
            # Public API tools (read-only) também só quando solicitado.
            if name.startswith(("knowledge.", "data.", "finance.", "news.", "papers.", "geo.", "time.")) and not asked_web:
                return True
        return False

    if _has_forbidden_tools(plan):
        # Tenta uma segunda vez instruindo explicitamente a responder só em texto.
        no_tools_msg = (
            user_message
            + "\n\nIMPORTANTE: o usuário NÃO pediu para ver/clicar na tela nem executar comandos. "
            + "Também NÃO pediu pesquisa/consulta na web/APIs. "
            + "Responda APENAS com orientação em texto, tool_calls=[] e risk=LOW."
        )
        plan2 = _route_with_llm_messages(
            settings,
            (context_messages or []) + [{"role": "user", "content": no_tools_msg}],
            **llm_kwargs,
        )
        if plan2 is not None and not _has_forbidden_tools(plan2) and (plan2.final_response or "").strip():
            plan = plan2
        else:
            # Fallback final: zera tools e devolve resposta textual (se existir).
            plan = plan.model_copy(
                update={
                    "intent": "chat",
                    "risk": RiskLevel.LOW,
                    "tool_calls": [],
                    "final_response": (plan.final_response or "").strip()
                    or "Posso te orientar em texto. Me diga o que você quer fazer e com quais detalhes.",
                }
            )

    # Safety guard: don't let the LLM trigger Discord actions unless the user asked.
    if any((c.tool_name or "").startswith("discord.") for c in plan.tool_calls):
        asked_discord = "discord" in norm
        asked_message = bool(_RE_DISCORD_MSG_HINT.search(norm))
        if not (asked_discord and asked_message):
            logger.warning("LLM plan attempted Discord tools without explicit user request; falling back")
            if heuristic_fallback is not None:
                return heuristic_fallback
            return Plan(intent="chat", user_message=user_message.strip(), tool_calls=[], risk=RiskLevel.LOW, final_response="Posso ajudar em texto. Se você quiser mesmo enviar mensagem no Discord, diga explicitamente o destinatário e a mensagem.")

    return plan


async def route_llm_async(
    settings: Settings,
    user_message: str,
    *,
    context_messages: list[dict[str, str]] | None = None,
    heuristic_fallback: Plan | None = None,
    registry: ToolRegistry | None = None,
    metrics: object | None = None,
    runlog: object | None = None,
    run: object | None = None,
) -> Plan | None:
    """Versão async do roteamento LLM.

    Preferência:
    - Usa `_route_with_llm_messages_async` (LiteLLM `acompletion`) quando possível.
    - Mantém a mesma lógica de guardrails/caches do `route_llm`.
    """

    # Observação: mantemos o cache/guardrails no `route_llm` sync.
    # Para não duplicar toda a função aqui, só usamos o caminho async nativo
    # quando houver contexto (caso típico do loop ReAct). Caso contrário,
    # o overhead de thread é baixo e preserva o cache persistente.
    if not context_messages:
        return await asyncio.to_thread(
            route_llm,
            settings,
            user_message,
            context_messages=context_messages,
            heuristic_fallback=heuristic_fallback,
            registry=registry,
            metrics=metrics,
            runlog=runlog,
            run=run,
        )

    # Sem cache para contexto (igual ao sync), mas evita bloquear a thread.
    llm_kwargs: dict[str, Any] = {}
    if registry is not None:
        llm_kwargs["registry"] = registry

    plan = await _route_with_llm_messages_async(
        settings,
        (context_messages or []) + [{"role": "user", "content": str(user_message or "").strip()}],
        **llm_kwargs,
    )
    if plan is None:
        return None
    return plan


def _route_heuristic(user_message: str, *, context_messages: list[dict[str, str]] | None = None) -> Plan:
    msg = user_message.strip()
    norm = _normalize(msg)

    # Chain of Responsibility (incremental): handlers pequenos e testáveis.
    # Se nenhum handler casar, seguimos com o roteador legado (bloco monolítico).
    try:
        handled = run_heuristic_handlers(user_message=msg, norm=norm, context_messages=context_messages)
        if handled is not None:
            return handled
    except Exception:
        # Fallback silencioso para manter robustez (o legado cobre o resto)
        pass

    def _infer_subject_from_context(ctx: list[dict[str, str]] | None) -> str | None:
        """Tenta inferir o assunto/entidade recente (best-effort).

        Ex.: após "você conhece a moeda PI Network?", um pedido "o gráfico da moeda"
        deve virar "Pi Network gráfico" ao pesquisar.
        """

        if not ctx:
            return None

        # Procura de trás para frente por menções explícitas.
        for m in reversed(ctx[-12:]):
            text = str(m.get("content") or "").strip()
            if not text:
                continue

            if re.search(r"\bpi\s*network\b", text, flags=re.IGNORECASE):
                return "Pi Network"

            # Outras criptos comuns (bem simples; evita NER pesado).
            for coin in ("Bitcoin", "Ethereum", "Solana", "Dogecoin", "Cardano", "XRP", "BNB"):
                if re.search(rf"\b{re.escape(coin)}\b", text, flags=re.IGNORECASE):
                    return coin

            # Heurística: "moeda X" / "criptomoeda X".
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

    def _guess_name_from_text(text: str) -> str | None:
        # quoted "Meu Projeto"
        q = re.search(r"['\"]([^'\"]{2,60})['\"]", text)
        if q:
            return q.group(1).strip()
        m = re.search(r"\b(chamado|chamada|nome)\b\s+([\w\- ]{2,60})", text, flags=re.IGNORECASE)
        if m:
            return (m.group(2) or "").strip()
        return None

        return Plan(
            intent="memory.profile_update",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="memory.profile_update", args={"patch": {"language": "en"}})],
            risk=RiskLevel.LOW,
            final_response="Ok — vou responder em inglês.",
        )

    if re.search(r"\b(responda\s+em|fale\s+em)\s+(portugues|português|pt\-br|brasil)\b", norm):
        return Plan(
            intent="memory.profile_update",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="memory.profile_update", args={"patch": {"language": "pt-BR"}})],
            risk=RiskLevel.LOW,
            final_response="Ok — vou responder em PT-BR.",
        )

    if re.search(r"\b(respostas\s+curtas|seja\s+curto|mais\s+curto|curtinho|objetivo)\b", norm):
        return Plan(
            intent="memory.profile_update",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="memory.profile_update", args={"patch": {"verbosity": "short"}})],
            risk=RiskLevel.LOW,
            final_response="Ok — vou ser mais curto e objetivo.",
        )

    if re.search(r"\b(mais\s+detalhado|bem\s+detalhado|detalhe|com\s+detalhes|explica\s+melhor)\b", norm):
        return Plan(
            intent="memory.profile_update",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="memory.profile_update", args={"patch": {"verbosity": "detailed"}})],
            risk=RiskLevel.LOW,
            final_response="Ok — vou responder com mais detalhes.",
        )

    def _guess_output_filename_for_ext(text: str, ext: str) -> str | None:
        # Prefer the *last* match for the requested extension.
        # Rationale: the message may contain the source PDF title and the desired output filename.
        ext = (ext or "").strip().lower().lstrip(".")
        if ext not in {"docx", "pdf"}:
            return None

        quoted = re.findall(rf"['\"]([^'\"]{{3,140}}\.{ext})['\"]", text, flags=re.IGNORECASE)
        if quoted:
            return (quoted[-1] or "").strip()

        bare = re.findall(rf"\b([^\s]{{3,140}}\.{ext})\b", text, flags=re.IGNORECASE)
        if bare:
            return (bare[-1] or "").strip()

        return None

    def _guess_pdf_title(text: str) -> str:
        pdf_title = ""
        q = re.search(r"['\"]([^'\"]{3,120}\.pdf)['\"]", text, flags=re.IGNORECASE)
        if q:
            pdf_title = (q.group(1) or "").strip()
        else:
            m = re.search(r"\b([^\s]{3,120}\.pdf)\b", text, flags=re.IGNORECASE)
            if m:
                pdf_title = (m.group(1) or "").strip()
        return pdf_title

    def _guess_word_title(text: str) -> str:
        word_title = "Word"
        wq = re.search(r"word\s*[:=]\s*['\"]([^'\"]{2,80})['\"]", text, flags=re.IGNORECASE)
        if wq:
            word_title = (wq.group(1) or "Word").strip() or "Word"
        return word_title

    # Regra: PDF (Google/Chrome) -> Word (digitar) ou gerar arquivo (.docx/.pdf)
    # Pedido explícito do usuário: ler/rolar o PDF e preencher/organizar as atividades.
    if re.search(r"\b(pdf)\b", norm) and re.search(
        r"\b(atividade|atividades|quest(ao|oes)|fazer|fa(c|ç)a|resolver|resolva|escrever|escreva)\b",
        norm,
    ):
        pdf_title = _guess_pdf_title(msg)
        assume_focused_pdf = False
        if not pdf_title:
            # UX melhor: se o usuário não souber o nome do arquivo, dá pra rodar assumindo
            # que ele colocou a janela do PDF em foco (ele vai aprovar via HITL antes).
            assume_focused_pdf = True

        wants_word = bool(re.search(r"\b(word)\b", norm))

        # Arquivo Word (.docx) pode aparecer como "docx", "docxs", ".docx" ou "arquivo do word".
        wants_docx = bool(
            re.search(r"\b(docx|docxs|\.docx)\b", norm)
            or (
                re.search(r"\b(gerar|criar|exportar|salvar|gera|gere|crie)\b", norm)
                and re.search(r"\b(arquivo|documento)\b", norm)
                and re.search(r"\b(word)\b", norm)
            )
        )

        # Arquivo PDF de saída: aceitar "gere um pdf" mesmo sem a palavra "arquivo".
        wants_pdf_file = bool(
            re.search(r"\b(gerar|criar|exportar|salvar|gera|gere|crie)\b", norm)
            and (
                re.search(r"\b(um\s+pdf|em\s+pdf|pdf)\b", norm)
                or ".pdf" in norm
            )
        )

        wants_desktop = bool(re.search(r"\b(área\s+de\s+trabalho|area\s+de\s+trabalho|desktop)\b", norm))

        # Opt-in para respostas completas via LLM quando o usuário pedir explicitamente "responda/solucione".
        wants_answers = bool(
            re.search(r"\b(responda|responder|respostas|solucione|solucionar|complete|completo|passo\s*a\s*passo)\b", norm)
        )

        # Se o usuário mencionou Word e não pediu explicitamente arquivo, digitamos no Word.
        if wants_word and not wants_docx and not wants_pdf_file:
            word_title = _guess_word_title(msg)
            return Plan(
                intent="edu.pdf_word_autofill",
                user_message=msg,
                tool_calls=[
                    ToolCall(
                        tool_name="edu.pdf_word_autofill",
                        args={
                            "pdf_title_contains": pdf_title,
                            "assume_focused_pdf": assume_focused_pdf,
                            "word_title_contains": word_title,
                            "output_mode": "word",
                            "solve_with_llm": wants_answers,
                            "llm_max_questions": 14,
                            "max_scrolls": 22,
                            "duration_s": 45.0,
                            "settle_ms": 650,
                        },
                    )
                ],
                risk=RiskLevel.HIGH,
                final_response=(
                    "Ok — vou ler o PDF (OCR + rolagem) e preencher organizado no Word (requer aprovação). "
                    + (
                        "Antes de aprovar: clique na janela do PDF para ela ficar em foco. "
                        if assume_focused_pdf
                        else ""
                    )
                    + "Dica: deixe o PDF visível em 100%-125% e o Word aberto."
                ),
            )

        # Caso contrário, só gera arquivo quando o usuário pediu explicitamente docx/pdf.
        if wants_docx or wants_pdf_file:
            output_mode = "docx" if wants_docx else "pdf"
            out_name = _guess_output_filename_for_ext(msg, output_mode)
            # Evita capturar o PDF de entrada como nome do arquivo de saída.
            if out_name and out_name.strip().lower() == pdf_title.strip().lower():
                out_name = None

            if not out_name:
                if wants_desktop:
                    out_name = "desktop:/atividades.docx" if output_mode == "docx" else "desktop:/atividades.pdf"
                else:
                    out_name = "data/tmp/atividades.docx" if output_mode == "docx" else "data/tmp/atividades.pdf"
            elif "/" not in out_name and "\\" not in out_name:
                # Se o usuário só deu o nome do arquivo, coloca em data/tmp (ou Desktop se pedido).
                out_name = f"desktop:/{out_name}" if wants_desktop else f"data/tmp/{out_name}"
            else:
                # Se ele forneceu um path, respeitamos; mas se pediu Desktop e não usou prefixo,
                # damos preferência ao prefixo (mais portátil/seguro) quando possível.
                if wants_desktop and not out_name.lower().startswith(("desktop:/", "downloads:/", "documents:/")):
                    leaf = out_name.replace("\\", "/").split("/")[-1]
                    if leaf and "." in leaf:
                        out_name = f"desktop:/{leaf}"

            return Plan(
                intent="edu.pdf_word_autofill",
                user_message=msg,
                tool_calls=[
                    ToolCall(
                        tool_name="edu.pdf_word_autofill",
                        args={
                            "pdf_title_contains": pdf_title,
                            "assume_focused_pdf": assume_focused_pdf,
                            "output_mode": output_mode,
                            "out_path": out_name,
                            "overwrite": True,
                            "solve_with_llm": wants_answers,
                            "llm_max_questions": 14,
                            "max_scrolls": 22,
                            "duration_s": 45.0,
                            "settle_ms": 650,
                        },
                    )
                ],
                risk=RiskLevel.HIGH,
                final_response=(
                    f"Ok — vou ler o PDF (OCR + rolagem) e gerar um arquivo {output_mode.upper()} (requer aprovação). "
                    + ("Antes de aprovar: clique na janela do PDF para ela ficar em foco. " if assume_focused_pdf else "")
                    + "Dica: deixe o PDF visível em 100%-125%."
                ),
            )

    # Regra: jogar o T-Rex (Chrome Dino) explicitamente
    # Mantemos determinístico para funcionar mesmo sem LLM (quota/rate limit).
    if re.search(r"\b(jogue|jogar|joga|joguei)\b", norm) and re.search(
        r"\b(t\s*-?\s*rex|trex|dino|dinossauro|chrome\s*dino|jogo\s*do\s*dinossauro)\b",
        norm,
    ):
        title_contains = None
        # Se o usuário fornecer um título de janela entre aspas, usamos como hint.
        m_quote = re.search(r"['\"]([^'\"]{2,80})['\"]", msg)
        if m_quote:
            title_contains = (m_quote.group(1) or "").strip()

        args: dict[str, Any] = {"duration_s": 30.0, "settle_ms": 450}
        if title_contains:
            args["title_contains"] = title_contains

        return Plan(
            intent="game.trex_autoplay",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="game.trex_autoplay", args=args)],
            risk=RiskLevel.HIGH,
            final_response="Ok — vou tentar jogar o T‑Rex automaticamente por ~30s (requer aprovação).",
        )

    # Regra: automação genérica de jogo (perfil/template)
    # Observação: não tentamos automação em contexto explicitamente online/competitivo.
    if re.search(r"\b(jogue|jogar|joga)\b", norm) and re.search(r"\b(jogo|game)\b", norm):
        if re.search(r"\b(online|competitivo|ranked|ranqueado|anti\s*-?cheat|multiplayer|pvp)\b", norm):
            return Plan(
                intent="chat",
                user_message=msg,
                tool_calls=[],
                risk=RiskLevel.LOW,
                final_response=(
                    "Posso orientar em texto, mas não vou automatizar jogos online/competitivos. "
                    "Se for um jogo offline/solo ou um jogo de navegador simples, diga isso explicitamente."
                ),
            )

        # Tenta inferir um nome de perfil simples.
        m_quote = re.search(r"['\"]([^'\"]{2,60})['\"]", msg)
        profile = (m_quote.group(1).strip().lower() if m_quote else "")

        # Se o usuário não forneceu um profile, fazemos calibração runner rápida via mouse.
        if not profile and re.search(r"\b(qualquer|qualquer\s+jogo)\b", norm):
            tmp_profile = "runner"
            return Plan(
                intent="game.autoplay",
                user_message=msg,
                tool_calls=[
                    ToolCall(tool_name="game.calibrate_runner_from_mouse", args={"name": tmp_profile, "jump_key": "space"}),
                    ToolCall(tool_name="game.autoplay", args={"profile": tmp_profile, "duration_s": 30.0, "settle_ms": 450}),
                ],
                risk=RiskLevel.HIGH,
                final_response=(
                    "Ok — antes de aprovar, coloque o mouse em cima do personagem do jogo. "
                    "Vou calibrar (runner) e jogar por ~30s (requer aprovação)."
                ),
            )

        args: dict[str, Any] = {"duration_s": 30.0, "settle_ms": 450}
        if profile:
            args["profile"] = profile
        else:
            args["template"] = "runner"

        return Plan(
            intent="game.autoplay",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="game.autoplay", args=args)],
            risk=RiskLevel.HIGH,
            final_response="Ok — vou tentar jogar automaticamente por ~30s (requer aprovação).",
        )

    def _strip_quotes(s: str) -> str:
        return (s or "").strip().strip('"').strip("'").strip()

    def _guess_folder_name(text: str) -> str | None:
        q = re.search(r"['\"]([^'\"]+)['\"]", text)
        if q:
            return q.group(1).strip()

        m2 = re.search(
            r"\b(pasta|diretorio|diret[oó]rio|folder|dir)\b\s+(?:chamada|chamado|nome)?\s*[: ]\s*(.+)$",
            text,
            flags=re.IGNORECASE,
        )
        if not m2:
            return None

        tail = (m2.group(2) or "").strip()
        # Remove sufixos de localização (ex: 'na área de trabalho', 'no disco D')
        tail = re.split(
            r"\b(no|na|em)\b\s+(?:[aá]rea de trabalho|desktop|disco|ssd|drive)\b",
            tail,
            flags=re.IGNORECASE,
        )[0].strip()
        return tail.strip().strip('"').strip("'")

    # NOTA: geração de código (ex.: exemplos completos de Java) é responsabilidade do modo LLM.
    # No modo heurístico, preferimos não chutar código nem “enfiar” templates fixos.

    # Regra: Fear & Greed — explícito
    # Exemplos: "fear and greed", "medo e ganância"
    if re.search(r"\b(fear\s*\&\s*greed|fear\s+and\s+greed|medo\s+e\s+gan[aâ]ncia|indice\s+de\s+medo)\b", norm):
        return Plan(
            intent="finance.fear_greed_index",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="finance.fear_greed_index", args={"limit": 1})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou buscar o índice Fear & Greed.",
        )

    # Regra: ISS — explícito
    # Exemplos: "onde está a ISS", "posição da iss"
    if re.search(r"\biss\b", norm) and re.search(r"\b(onde|posi[cç][aã]o|localiza[cç][aã]o|agora|neste\s+momento)\b", norm):
        return Plan(
            intent="space.iss_position",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="space.iss_position", args={})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou buscar a posição atual da ISS.",
        )

    # Regra: terremotos (USGS) — explícito
    # Exemplos: "terremotos últimos 7 dias", "sismos magnitude 5"
    if re.search(r"\b(terremoto|terremotos|sismo|sismos|earthquake|earthquakes)\b", norm):
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
            tool_calls=[ToolCall(tool_name="science.earthquake_usgs", args={"days": days, "min_magnitude": min_mag, "limit": 10})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou listar terremotos recentes (USGS).",
        )

    # Regra: COVID — explícito
    # Exemplos: "covid no brasil", "covid global"
    m = re.search(r"\b(covid)\b(?:\s+(no|na|em)\s+(.+))?$", msg, flags=re.IGNORECASE)
    if m:
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

    # Regra: GitHub Status — explícito
    if re.search(r"\bgithub\b", norm) and re.search(r"\bstatus\b", norm):
        return Plan(
            intent="status.github",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="status.github", args={})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou consultar o status do GitHub.",
        )

    # Regra: Cloudflare Status — explícito
    if re.search(r"\bcloudflare\b", norm) and re.search(r"\bstatus\b", norm):
        return Plan(
            intent="status.cloudflare",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="status.cloudflare", args={})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou consultar o status do Cloudflare.",
        )

    # (migrado) Discord Status — handler determinístico em `core.heuristic_handlers`

    # Regra: Docker Status — explícito
    if re.search(r"\bdocker\b", norm) and re.search(r"\bstatus\b", norm):
        return Plan(
            intent="status.docker",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="status.docker", args={})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou consultar o status do Docker.",
        )

    # Regra: Atlassian Status — explícito
    if re.search(r"\batlassian\b", norm) and re.search(r"\bstatus\b", norm):
        return Plan(
            intent="status.atlassian",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="status.atlassian", args={})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou consultar o status da Atlassian.",
        )

    # Regra: Zoom Status — explícito
    if re.search(r"\bzoom\b", norm) and re.search(r"\bstatus\b", norm):
        return Plan(
            intent="status.zoom",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="status.zoom", args={})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou consultar o status do Zoom.",
        )

    # Regra: GitLab Status — explícito
    if re.search(r"\bgitlab\b", norm) and re.search(r"\bstatus\b", norm):
        return Plan(
            intent="status.gitlab",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="status.gitlab", args={})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou consultar o status do GitLab.",
        )

    # Regra: npm Status — explícito
    if re.search(r"\bnpm\b", norm) and re.search(r"\bstatus\b", norm):
        return Plan(
            intent="status.npm",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="status.npm", args={})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou consultar o status do npm.",
        )

    # Regra: OpenAI Status — explícito
    if re.search(r"\bopen\s*ai\b|\bopenai\b", norm) and re.search(r"\bstatus\b", norm):
        return Plan(
            intent="status.openai",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="status.openai", args={})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou consultar o status da OpenAI.",
        )


    # Regra: Art Institute of Chicago — explícito
    m = re.search(r"\b(art\s*institute\s*of\s*chicago|aic|artic)\b\s*[:\-]\s*(.+)$", msg, flags=re.IGNORECASE)
    if m and (m.group(2) or "").strip():
        q = (m.group(2) or "").strip().strip('"\'')
        return Plan(
            intent="art.artic_search",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="art.artic_search", args={"query": q, "limit": 5})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou buscar no acervo do Art Institute of Chicago.",
        )

    # Regra: Chess.com — explícito
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

    # Regra: Open Brewery DB — explícito
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

    # Regra: Deck of Cards — explícito
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

    # Regras: fun (quotes / advice / bored / imagens)
    if re.fullmatch(r"(quote|citacao|frase)(?:\s+(aleatoria|random))?", norm or ""):
        return Plan(
            intent="fun.quote_random",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="fun.quote_random", args={})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou pegar uma quote aleatória.",
        )

    if re.fullmatch(r"(conselho|advice)", norm or ""):
        return Plan(
            intent="fun.advice",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="fun.advice", args={})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou pegar um conselho aleatório.",
        )

    if re.fullmatch(r"(entediado|bored)", norm or ""):
        return Plan(
            intent="fun.bored_activity",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="fun.bored_activity", args={})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou sugerir uma atividade aleatória.",
        )

    if re.fullmatch(r"(raposa|fox)(?:\s+(imagem|image))?", norm or ""):
        return Plan(
            intent="fun.fox_image",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="fun.fox_image", args={})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou pegar uma imagem aleatória de raposa.",
        )

    if re.fullmatch(r"(pato|duck)(?:\s+(imagem|image))?", norm or ""):
        return Plan(
            intent="fun.duck_image",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="fun.duck_image", args={})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou pegar uma imagem aleatória de pato.",
        )


    # Regra: Scryfall (Magic) — explícito
    if re.search(r"\b(scryfall|mtg)\b", norm) and re.search(r"\b(random|aleatoria|aleatória)\b", norm):
        return Plan(
            intent="cards.scryfall_random",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="cards.scryfall_random", args={})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou pegar uma carta aleatória (Scryfall).",
        )

    m = re.search(r"\b(scryfall|mtg)\b\s*[:\-]\s*(.+)$", msg, flags=re.IGNORECASE)
    if m and (m.group(2) or "").strip():
        q = (m.group(2) or "").strip().strip('"\'')
        return Plan(
            intent="cards.scryfall_search",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="cards.scryfall_search", args={"query": q, "limit": 5})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou buscar cartas (Scryfall).",
        )

    # Regra: Rick and Morty — explícito
    m = re.search(r"\b(rick\s*&\s*morty|rick\s+and\s+morty|rickmorty)\b\s*[:\-]\s*(.+)$", msg, flags=re.IGNORECASE)
    if m and (m.group(2) or "").strip():
        q = (m.group(2) or "").strip().strip('"\'')
        return Plan(
            intent="media.rickmorty_character_search",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="media.rickmorty_character_search", args={"query": q, "limit": 5})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou buscar personagens de Rick and Morty.",
        )

    # Regra: Sunrise/Sunset — explícito
    # Exemplos: "sunrise: -23.55, -46.63", "nascer do sol: -23.55 -46.63"
    m = re.search(r"\b(sunrise|sunset|nascer\s+do\s+sol|por\s+do\s+sol)\b\s*[:\-]\s*(-?\d+(?:[\.,]\d+)?)\s*[,\s]+\s*(-?\d+(?:[\.,]\d+)?)\b", msg, flags=re.IGNORECASE)
    if m:
        lat_s = (m.group(2) or "").replace(",", ".")
        lon_s = (m.group(3) or "").replace(",", ".")
        try:
            lat = float(lat_s)
            lon = float(lon_s)
        except Exception:
            lat = None
            lon = None
        if lat is not None and lon is not None:
            return Plan(
                intent="time.sunrise_sunset",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="time.sunrise_sunset", args={"lat": lat, "lon": lon})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou consultar horários de nascer/pôr do sol (UTC).",
            )

    # Regra: DadJoke / JokeAPI — explícito
    if re.search(r"\bdadjoke\b", norm):
        return Plan(
            intent="fun.dadjoke",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="fun.dadjoke", args={})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou pegar uma dad joke aleatória.",
        )

    if re.search(r"\bjokeapi\b", norm):
        return Plan(
            intent="fun.jokeapi",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="fun.jokeapi", args={"category": "Any"})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou pegar uma piada aleatória (safe-mode).",
        )

    # (migrado) IBGE estados/municípios — handler determinístico em `core.heuristic_handlers`

    # Regra: ViaCEP — explícito
    m = re.search(r"\b(cep|viacep)\b\s*[:\-]?\s*(\d{5}-?\d{3})\b", msg, flags=re.IGNORECASE)
    if m and (m.group(2) or "").strip():
        cep = (m.group(2) or "").strip()
        return Plan(
            intent="br.viacep_lookup",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="br.viacep_lookup", args={"cep": cep})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou consultar o endereço pelo CEP (ViaCEP).",
        )

    # Regra: Gutendex / Gutenberg — explícito
    m = re.search(r"\b(gutendex|gutenberg|project\s+gutenberg)\b\s*[:\-]\s*(.+)$", msg, flags=re.IGNORECASE)
    if m and (m.group(2) or "").strip():
        q = (m.group(2) or "").strip().strip('"\'')
        return Plan(
            intent="books.gutendex_search",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="books.gutendex_search", args={"query": q, "limit": 5})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou buscar livros no Project Gutenberg (Gutendex).",
        )

    # Regra: OpenFoodFacts — explícito
    m = re.search(r"\b(open\s*food\s*facts|openfoodfacts|off)\b\s*[:\-]\s*(.+)$", msg, flags=re.IGNORECASE)
    if m and (m.group(2) or "").strip():
        q = (m.group(2) or "").strip().strip('"\'')
        return Plan(
            intent="data.openfoodfacts_search",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="data.openfoodfacts_search", args={"query": q, "limit": 5})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou buscar produtos no OpenFoodFacts.",
        )

    # Regra: npm downloads — explícito
    m = re.search(r"\bnpm\b\s+downloads\b\s*[:\-]\s*(@?[\w\-\.]+(?:/[\w\-\.]+)?)\b", msg, flags=re.IGNORECASE)
    if m and (m.group(1) or "").strip():
        pkg = (m.group(1) or "").strip()
        return Plan(
            intent="pkg.npm_downloads_last_week",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="pkg.npm_downloads_last_week", args={"package": pkg})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou buscar downloads last-week do pacote no npm.",
        )

    # Regra: GitHub repo search — explícito
    # Exemplos: "github: agentic workflow", "github repo: typer rich"
    m = re.search(r"\b(github)(?:\s+repo|\s+repos|\s+reposit[oó]rios?)?\b\s*[:\-]?\s*(.+)$", msg, flags=re.IGNORECASE)
    if m and (m.group(2) or "").strip():
        q = (m.group(2) or "").strip().strip('"\'')
        return Plan(
            intent="code.github_repo_search",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="code.github_repo_search", args={"query": q, "limit": 5})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou buscar repositórios no GitHub.",
        )

    # Regra: StackOverflow/StackExchange — explícito
    # Exemplos: "stackoverflow: error list index out of range"
    m = re.search(r"\b(stack\s*overflow|stackoverflow|stackexchange)\b\s*[:\-]?\s*(.+)$", msg, flags=re.IGNORECASE)
    if m and (m.group(2) or "").strip():
        q = (m.group(2) or "").strip().strip('"\'')
        return Plan(
            intent="qa.stackexchange_search",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="qa.stackexchange_search", args={"query": q, "limit": 5})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou buscar perguntas relevantes no StackOverflow.",
        )

    # Regra: dicionário / definir palavra — explícito
    # Exemplos: "dicionário: ephemeral", "defina recursion", "significado de latency"
    m = re.search(r"\b(dicion[aá]rio|dictionary|defina|definir|significado)\b\s*(?:de\s+)?[:\-]?\s*([\w\-]{2,60})\b", msg, flags=re.IGNORECASE)
    if m and (m.group(2) or "").strip():
        term = (m.group(2) or "").strip().strip('"\'')
        return Plan(
            intent="language.dictionary_define",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="language.dictionary_define", args={"term": term, "lang": "en"})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou buscar a definição no dicionário.",
        )

    # Regra: letras (lyrics) — explícito
    # Exemplos: "letra: Queen - Bohemian Rhapsody", "lyrics: Adele - Hello"
    m = re.search(r"\b(letra|lyrics)\b\s*[:\-]?\s*(.+?)\s*[-–]\s*(.+)$", msg, flags=re.IGNORECASE)
    if m:
        artist = (m.group(2) or "").strip().strip('"\'')
        title = (m.group(3) or "").strip().strip('"\'')
        if artist and title:
            return Plan(
                intent="media.lyrics",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="media.lyrics", args={"artist": artist, "title": title})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar a letra da música.",
            )

    # Regra: piada — explícito
    if re.search(r"\b(piada|joke)\b", norm):
        return Plan(
            intent="fun.joke",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="fun.joke", args={})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou pegar uma piada.",
        )

    # Regra: trivia / quiz — explícito
    if re.search(r"\b(trivia|quiz)\b", norm):
        return Plan(
            intent="fun.trivia",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="fun.trivia", args={"amount": 5, "type": "multiple"})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou pegar perguntas de trivia.",
        )

    # Regra: Pokémon — explícito
    # Exemplos: "pokemon: pikachu", "pokemon 25"
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

    # Regra: RIPEstat (network info) — explícito
    # Exemplos: "ripestat ip: 8.8.8.8", "ripe stat asn: 15169"
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

    # Regra: IP info — explícito
    # Exemplos: "meu ip", "ip: 8.8.8.8"
    if re.search(r"\b(meu\s+ip|ip\s+p[úu]blico|ip\s+publico)\b", norm):
        return Plan(
            intent="net.ip_info",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="net.ip_info", args={})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou consultar informações do IP.",
        )
    # Evita conflito com comandos mais específicos (rdap/bgp).
    if all(k not in norm for k in ("rdap", "whois", "bgp", "ripestat", "ripe stat")):
        m = re.search(r"\bip\b\s*[:\-]?\s*(\d{1,3}(?:\.\d{1,3}){3})\b", msg, flags=re.IGNORECASE)
        if m and (m.group(1) or "").strip():
            return Plan(
                intent="net.ip_info",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="net.ip_info", args={"ip": (m.group(1) or "").strip()})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou consultar informações do IP.",
            )

    # Regra: pessoa aleatória — explícito
    # Exemplos: "pessoa aleatória", "random user"
    if re.search(r"\b(pessoa\s+aleat[oó]ria|random\s+user)\b", norm):
        return Plan(
            intent="people.random_user",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="people.random_user", args={})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou gerar uma pessoa aleatória.",
        )

    # Regra: cat fact — explícito
    if re.search(r"\b(cat\s*fact|fato\s+de\s+gato|curiosidade\s+de\s+gato)\b", norm):
        return Plan(
            intent="fun.cat_fact",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="fun.cat_fact", args={})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou pegar uma curiosidade sobre gatos.",
        )

    # Regra: QR code URL — explícito
    # Exemplos: "qr: https://example.com", "qrcode: oi"
    m = re.search(r"\b(qr\s*code|qrcode|qr)\b\s*[:\-]?\s*(.+)$", msg, flags=re.IGNORECASE)
    if m and (m.group(2) or "").strip():
        payload = (m.group(2) or "").strip().strip('"\'')
        return Plan(
            intent="utils.qr_code_url",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="utils.qr_code_url", args={"data": payload, "size": "200x200"})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou gerar uma URL de QR code.",
        )

    # Regra: OSV vuln by ID — explícito
    # Exemplos: "cve-2024-1234", "GHSA-xxxx-xxxx-xxxx", "osv: OSV-2020-744"
    # Guard: quando o usuário pede KEV explicitamente, isso deve ganhar do OSV.
    m = re.search(r"\b(osv|vuln|vulnerability)\b\s*[:\-]?\s*([A-Za-z0-9\-\.]{6,80})\b", msg, flags=re.IGNORECASE)
    if m and (m.group(2) or "").strip() and not re.search(r"\b(cisa\s+kev|kev)\b", norm):
        vid = (m.group(2) or "").strip().upper()
        if re.fullmatch(r"(?:CVE|GHSA|OSV)[A-Z0-9\-\.]{4,76}", vid) or vid.startswith(("CVE-", "GHSA-", "OSV-")):
            return Plan(
                intent="sec.osv_vuln",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="sec.osv_vuln", args={"id": vid})],
                risk=RiskLevel.MEDIUM,
                final_response="Ok — vou buscar detalhes da vulnerabilidade (OSV.dev).",
            )

    m = re.search(r"\b(CVE-\d{4}-\d{3,10}|GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}|OSV-\d{4}-\d+)\b", msg, flags=re.IGNORECASE)
    if m and (m.group(1) or "").strip() and not re.search(r"\b(cisa\s+kev|kev)\b", norm):
        vid = (m.group(1) or "").strip().upper()
        return Plan(
            intent="sec.osv_vuln",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="sec.osv_vuln", args={"id": vid})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou buscar detalhes da vulnerabilidade (OSV.dev).",
        )

    # Regra: OSV query por pacote+versão — explícito
    # Formato simples: "osv: PyPI jinja2 3.1.4" | "osv npm express 4.18.2" | "osv crates tokio 1.35.1"
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
            tool_calls=[ToolCall(tool_name="sec.osv_query", args={"ecosystem": eco, "name": name, "version": ver, "limit": 10})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou checar vulnerabilidades para essa versão (OSV.dev).",
        )

    # Regra: PyPI project — explícito
    # Exemplos: "pypi: requests", "pip: fastapi"
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

    # Regra: npm package — explícito
    # Exemplos: "npm: express", "npm: @types/node"
    m = re.search(r"\b(npm)\b\s*[:\-]?\s*([^\s]{1,160})\b", msg, flags=re.IGNORECASE)
    if m and (m.group(2) or "").strip():
        pkg = (m.group(2) or "").strip()
        return Plan(
            intent="pkg.npm_package",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="pkg.npm_package", args={"name": pkg})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou buscar metadados do pacote no npm registry.",
        )

    # Regra: crates.io crate — explícito
    # Exemplos: "crates: tokio", "crates.io: serde"
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

    # Regra: DNS resolve — explícito
    # Exemplos: "dns: example.com A", "resolve: example.com MX"
    m = re.search(r"\b(dns|resolve)\b\s*[:\-]?\s*([A-Za-z0-9\-\.]{1,253})(?:\s+(A|AAAA|CNAME|MX|TXT))?$", msg, flags=re.IGNORECASE)
    if m and (m.group(2) or "").strip():
        host = (m.group(2) or "").strip().strip('"\'').rstrip('.')
        rtype = (m.group(3) or "A").strip().upper()
        return Plan(
            intent="net.dns_google_resolve",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="net.dns_google_resolve", args={"name": host, "type": rtype})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou resolver DNS via Google (DoH).",
        )

    # Regra: RDAP (whois moderno) — explícito
    # Exemplos: "rdap domain: example.com", "whois: example.com"
    m = re.search(r"\b(rdap\s+domain|rdap|whois)\b\s*[:\-]?\s*([A-Za-z0-9\-\.]{1,253}\.[A-Za-z]{2,24})\b", msg, flags=re.IGNORECASE)
    if m and (m.group(2) or "").strip():
        domain = (m.group(2) or "").strip().strip('"\'').rstrip('.')
        return Plan(
            intent="net.rdap_domain",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="net.rdap_domain", args={"domain": domain})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou consultar RDAP para esse domínio.",
        )

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

    # Regra: PeeringDB — explícito
    # Exemplos: "peeringdb asn: 15169", "peering db: 15169"
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

    # Regra: BGP/ASN (bgpview) — explícito
    # Exemplos: "bgp ip: 8.8.8.8", "asn: 15169"
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

    m = re.search(r"\b(asn|bgp\s*asn)\b\s*[:\-]?\s*(?:AS)?(\d{1,10})\b", msg, flags=re.IGNORECASE)
    if m and (m.group(2) or "").strip():
        asn = (m.group(2) or "").strip()
        return Plan(
            intent="net.bgpview_asn",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="net.bgpview_asn", args={"asn": asn})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou consultar informações desse ASN.",
        )

    # Regra: Certificate Transparency (crt.sh) — explícito
    # Exemplos: "crtsh: example.com", "certificados: example.com"
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

    # Regra: URLhaus — explícito
    # Exemplos: "urlhaus url: http://example.com/bad", "urlhaus host: example.com"
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
        host = (m.group(1) or "").strip().strip('"\'').rstrip('.')
        return Plan(
            intent="sec.urlhaus_host",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="sec.urlhaus_host", args={"host": host})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou consultar o URLhaus para esse host.",
        )

    # Regra: ThreatFox IOC — explícito
    # Exemplos: "threatfox: 1.2.3.4", "threatfox ioc: abc"
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

    # Regra: Feodo Tracker (botnet C2 IP:porta) — explícito
    # Exemplos: "feodotracker", "feodo tracker list"
    if re.search(r"\bfeodo\b", norm) and re.search(r"\btracker\b", norm):
        return Plan(
            intent="sec.feodotracker_ip_blocklist",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="sec.feodotracker_ip_blocklist", args={"limit": 20})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou buscar a blocklist do Feodo Tracker.",
        )

    # Regra: Hashlookup (CIRCL) — explícito
    # Exemplos: "hashlookup sha256: <hash>", "hash lookup: <sha1>"
    if re.search(r"\bhash\s*lookup\b|\bhashlookup\b", norm):
        algo = ""
        if re.search(r"\bsha\s*256\b|\bsha256\b", norm):
            algo = "sha256"
        elif re.search(r"\bsha\s*1\b|\bsha1\b", norm):
            algo = "sha1"
        elif re.search(r"\bmd5\b", norm):
            algo = "md5"

        m = re.search(r"\b([0-9a-fA-F]{32}|[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\b", msg)
        if m and (m.group(1) or "").strip():
            h = (m.group(1) or "").strip().lower()
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

    # Regra: CISA KEV — explícito
    # Exemplos: "kev: CVE-2021-44228", "cisa kev log4j"
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

    # Regra: abrir Explorador / gerenciador de arquivos
    if re.search(r"\b(explorador|explorer|gerenciador de arquivos|arquivos)\b", norm) and re.search(
        r"\b(abrir|abra|abre|open)\b", norm
    ):
        return Plan(
            intent="os.open_explorer",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="os.open_explorer", args={"path": "."})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok, abri o Explorador de Arquivos.",
        )

    # Regra: abrir alvos potencialmente perigosos (sempre pede HITL)
    if re.search(r"\b(abrir|abra|abre|open)\b", norm):
        dangerous_map = {
            "cmd": r"\b(cmd|prompt de comando|command prompt)\b",
            "powershell": r"\b(power\s*shell|powershell)\b",
            "pwsh": r"\b(pwsh)\b",
            "terminal": r"\b(windows terminal|terminal)\b",
            "regedit": r"\b(regedit|editor do registro|registro)\b",
        }
        for app_key, pat in dangerous_map.items():
            if re.search(pat, norm):
                return Plan(
                    intent="os.open_app",
                    user_message=msg,
                    tool_calls=[ToolCall(tool_name="os.open_app", args={"app": app_key})],
                    risk=RiskLevel.CRITICAL,
                    final_response="Ok — vou abrir isso (requer aprovação).",
                )

    # Regra: gerar allowlist de apps automaticamente
    if re.search(r"\b(gerar|criar|montar)\b.*\b(allowlist|lista)\b.*\b(app|apps|programa|programas)\b", norm):
        return Plan(
            intent="os.generate_open_apps",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="os.generate_open_apps", args={"out_path": "data/open_apps.generated.json", "overwrite": True})],
            risk=RiskLevel.HIGH,
            final_response="Ok. Vou gerar um arquivo JSON com apps detectados para sua allowlist.",
        )

    # Regra: mapear programas abertos (janelas + processos)
    if re.search(r"\b(apps?|programas?)\b", norm) and re.search(
        r"\b(abertos?|aberta|rodando|em execucao|executando|em uso|ativos?)\b", norm
    ) and re.search(r"\b(listar|lista|mostrar|ver|mapear|mapa)\b", norm):
        return Plan(
            intent="win.list_windows",
            user_message=msg,
            tool_calls=[
                ToolCall(tool_name="win.list_windows", args={"visible_only": True, "max_results": 200}),
                ToolCall(tool_name="os.list_processes", args={"max_results": 300}),
            ],
            risk=RiskLevel.LOW,
            final_response="Ok — vou mapear as janelas abertas e os processos em execução.",
        )

    # Regra: listar apps instalados/atalhos
    if re.search(r"\b(listar|lista|mostrar|ver)\b.*\b(apps|programas)\b", norm) and re.search(
        r"\b(instalados|atalhos|menu iniciar|menu|start)\b", norm
    ):
        # Se o usuário pediu explicitamente "instalados", preferimos o inventário via Registro.
        if re.search(r"\binstalados\b", norm) and not re.search(r"\b(atalhos|menu iniciar|start)\b", norm):
            return Plan(
                intent="os.list_installed_apps",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="os.list_installed_apps", args={"max_results": 800})],
                risk=RiskLevel.LOW,
                final_response="Ok — vou listar apps instalados (via Registro do Windows).",
            )

        return Plan(
            intent="os.scan_apps",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="os.scan_apps", args={"max_results": 400})],
            risk=RiskLevel.LOW,
            final_response="Ok, vou listar atalhos de apps detectados.",
        )

    # Regra: abrir YouTube no navegador padrão
    if "youtube" in norm and re.search(r"\b(abrir|abra|abre|open)\b", norm):
        return Plan(
            intent="os.open_url",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="os.open_url", args={"url": "https://www.youtube.com/"})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok, abri o YouTube no seu navegador.",
        )

    # Regra: pesquisar no Google (abre no navegador padrão)
    # Mantemos determinístico para funcionar mesmo sem LLM (quota/rate limit).
    if re.search(r"\bgoogle\b", norm) and re.search(
        r"\b(pesquise|pesquisa|procure|buscar|busque|verifique|veja|analise|abra|abre|abrir)\b",
        norm,
    ):
        q: str | None = None

        m = re.search(r"\bgoogle\b\s*[:\-]\s*(.+)$", msg, flags=re.IGNORECASE)
        if m:
            q = (m.group(1) or "").strip()

        if not q:
            m = re.search(r"\b(?:no|na|em)\s+google\b\s*(?:sobre\s+)?(.+)$", msg, flags=re.IGNORECASE)
            if m:
                q = (m.group(1) or "").strip()

        if not q:
            # Remove boilerplate e usa o resto como query.
            q2 = msg
            q2 = re.sub(r"\b(?:no|na|em)\s+google\b", "", q2, flags=re.IGNORECASE)
            q2 = re.sub(r"\b(por\s+favor|pfv|porfavor)\b", "", q2, flags=re.IGNORECASE)
            q2 = re.sub(
                r"\b(pesquise|pesquisa|procure|buscar|busque|verifique|veja|analise|abra|abre|abrir)\b",
                "",
                q2,
                flags=re.IGNORECASE,
            )
            q = q2.strip(" \t\n\r.,;:!?-")

        # Se ainda ficou genérico demais, tenta inferir assunto recente.
        if not q or len(q) < 3 or _normalize(q) in {"grafico", "gráfico", "grafico de moeda", "gráfico de moeda", "moeda", "grafico da moeda", "gráfico da moeda"}:
            subj = _infer_subject_from_context(context_messages)
            if subj:
                # Se o usuário mencionou gráfico, preserva isso.
                if re.search(r"\b(grafico|gráfico|chart|price)\b", norm):
                    q = f"{subj} gráfico"
                else:
                    q = subj
            else:
                q = q or "gráfico de moeda"

        url = "https://www.google.com/search?q=" + quote_plus(q)
        return Plan(
            intent="os.open_url",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="os.open_url", args={"url": url})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok — vou abrir uma pesquisa no Google no seu navegador.",
        )

    # Regra: abrir calculadora do Windows
    if re.search(r"\b(calculadora|calculator|calc)\b", norm) and re.search(
        r"\b(abrir|abra|abre|open)\b", norm
    ):
        return Plan(
            intent="os.open_app",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="os.open_app", args={"app": "calculator"})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok, abri a Calculadora do Windows.",
        )

    # Regra: abrir VS Code
    if re.search(r"\b(vs\s*code|vscode|visual\s+studio\s+code)\b", norm) and re.search(
        r"\b(abrir|abra|abre|open)\b", norm
    ):
        return Plan(
            intent="os.open_app",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="os.open_app", args={"app": "vscode"})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok, vou abrir o VS Code.",
        )

    # VS Code: listar extensões
    if re.search(r"\b(vs\s*code|vscode|visual\s+studio\s+code)\b", norm) and re.search(
        r"\b(extens(ao|oes)|extensions?)\b", norm
    ) and re.search(r"\b(listar|liste|mostrar|mostre|ver|veja)\b", norm):
        return Plan(
            intent="vscode.list_extensions",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="vscode.list_extensions", args={"show_versions": True})],
            risk=RiskLevel.LOW,
            final_response="Ok — vou listar as extensões instaladas no VS Code.",
        )

    # VS Code: instalar/remover extensão por id (publisher.name)
    if re.search(r"\b(extens(ao|oes)|extensions?)\b", norm) and re.search(r"\b(instalar|instale|instala|adicionar|adicione|adiciona)\b", norm):
        m = re.search(r"([A-Za-z0-9][A-Za-z0-9\-]*\.[A-Za-z0-9][A-Za-z0-9\-\.]*)", msg)
        if m:
            ext_id = (m.group(1) or "").strip()
            return Plan(
                intent="vscode.install_extension",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="vscode.install_extension", args={"extension_id": ext_id})],
                risk=RiskLevel.HIGH,
                final_response=f"Ok — vou instalar a extensão {ext_id} no VS Code.",
            )

    if re.search(r"\b(extens(ao|oes)|extensions?)\b", norm) and re.search(r"\b(remover|remove|desinstalar|desinstale|uninstall)\b", norm):
        m = re.search(r"([A-Za-z0-9][A-Za-z0-9\-]*\.[A-Za-z0-9][A-Za-z0-9\-\.]*)", msg)
        if m:
            ext_id = (m.group(1) or "").strip()
            return Plan(
                intent="vscode.uninstall_extension",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="vscode.uninstall_extension", args={"extension_id": ext_id})],
                risk=RiskLevel.HIGH,
                final_response=f"Ok — vou remover a extensão {ext_id} do VS Code.",
            )

    # VS Code: ler settings.json do workspace
    if re.search(r"\b(vs\s*code|vscode|visual\s+studio\s+code)\b", norm) and re.search(
        r"\b(settings\.json|settings|configurac(ao|oes)|config)\b", norm
    ) and re.search(r"\b(ler|leia|mostrar|mostre|ver|veja)\b", norm):
        return Plan(
            intent="vscode.settings_read",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="vscode.settings_read", args={})],
            risk=RiskLevel.LOW,
            final_response="Ok — vou ler o .vscode/settings.json deste workspace.",
        )

    # VS Code: ler tasks.json do workspace
    if re.search(r"\b(vs\s*code|vscode|visual\s+studio\s+code)\b", norm) and re.search(
        r"\b(tasks\.json|tasks|tarefas)\b", norm
    ) and re.search(r"\b(ler|leia|mostrar|mostre|ver|veja)\b", norm):
        return Plan(
            intent="vscode.tasks_read",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="vscode.tasks_read", args={})],
            risk=RiskLevel.LOW,
            final_response="Ok — vou ler o .vscode/tasks.json deste workspace.",
        )

    # VS Code: ler launch.json do workspace
    if re.search(r"\b(vs\s*code|vscode|visual\s+studio\s+code)\b", norm) and re.search(
        r"\b(launch\.json|launch|debug|depurar|depurac(ao|oes))\b", norm
    ) and re.search(r"\b(ler|leia|mostrar|mostre|ver|veja)\b", norm):
        return Plan(
            intent="vscode.launch_read",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="vscode.launch_read", args={})],
            risk=RiskLevel.LOW,
            final_response="Ok — vou ler o .vscode/launch.json deste workspace.",
        )

    # (migrado) Discord open/close/send — handlers determinísticos em `core.heuristic_handlers`

    # Regra: pedidos de geração de código (matriz/matemática/etc.)
    # - Em modo heurístico: não chutamos templates fixos.
    # - Em modo llm: a heurística retorna chat (não determinístico) e o `route()` chama o LLM.
    if re.search(r"\b(criar|crie|cria|fazer|faca|faça|gerar|gere|escrever|escreva|montar)\b", norm):
        wants_code = bool(re.search(r"\b(c[oó]digo|codigo)\b", norm))
        wants_jgrasp = ("jgrasp" in norm)
        wants_matrix_math = bool(re.search(r"\b(matriz|matrix|matem[aá]tica|matematica|math)\b", norm))
        wants_conta_math = bool(re.search(r"\bconta\b", norm)) and not bool(
            re.search(r"\b(login|senha|email|e-mail|conta\s+banc[aá]ria|banco|cadastro|registrar)\b", norm)
        )

        if wants_code and (wants_matrix_math or (wants_jgrasp and wants_conta_math) or (wants_matrix_math and not wants_jgrasp)):
            return Plan(
                intent="chat",
                user_message=msg,
                tool_calls=[],
                risk=RiskLevel.LOW,
                final_response=(
                    "Consigo gerar esse código, mas no modo heurístico eu não uso templates fixos. "
                    "Ative o modo LLM (OMNI_ROUTER_MODE=llm) e repita o pedido, ou descreva exatamente o que o programa deve fazer "
                    "(entradas, saídas e restrições) que eu te guio passo a passo."
                ),
            )

    # (migrado) jGRASP hello-world determinístico — handler em `core.heuristic_handlers`

    # (migrado) Discord send_message — handler determinístico em `core.heuristic_handlers`

    # Regra: OCR
    if re.search(r"\b(ocr|ler tela|leia a tela|o que esta escrito|o que esta na tela)\b", norm):
        return Plan(
            intent="vision.ocr",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="screen.ocr", args={})],
            risk=RiskLevel.MEDIUM,
            final_response="Fiz OCR da tela atual.",
        )

    # Regra: criar pasta (mkdir)
    m = re.search(
        r"\b(criar|crie|cria|make|mkdir)\b.*\b(pasta|diretorio|diret[oó]rio|folder|dir)\b",
        msg,
        flags=re.IGNORECASE,
    )
    if m:
        name = _guess_folder_name(msg)
        if not name:
            return Plan(
                intent="chat",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="echo", args={"text": msg})],
                risk=RiskLevel.LOW,
                final_response="Qual nome da pasta? (ex: criar pasta: data/minha_pasta)",
            )

        # Desktop/Área de Trabalho (resolve via Known Folder; inclui OneDrive redirecionado)
        if re.search(r"\b([aá]rea de trabalho|desktop)\b", norm):
            return Plan(
                intent="os.mkdir",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="os.mkdir", args={"known_folder": "desktop", "name": name})],
                risk=RiskLevel.HIGH,
                final_response=f"Ok, criei a pasta na Área de Trabalho: {name}",
            )

        # Drive específico (ex: D:, 'disco D', 'SSD (D:)')
        drive = None
        m_drive = re.search(r"\b([c-zC-Z])\s*:\b", msg)
        if m_drive:
            drive = m_drive.group(1).upper()
        else:
            m_drive2 = re.search(r"\bdisco\s+([c-z])\b", norm)
            if m_drive2:
                drive = m_drive2.group(1).upper()
            elif re.search(r"\bssd\b", norm) and re.search(r"\b[dD]\b", msg):
                drive = "D"

        if drive:
            return Plan(
                intent="os.mkdir",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="os.mkdir", args={"path": f"{drive}:/{name}"})],
                risk=RiskLevel.HIGH,
                final_response=f"Ok, criei a pasta em {drive}:\\{name}",
            )

        # Default: workspace
        rel = name.replace("\\", "/")
        return Plan(
            intent="fs.mkdir",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="fs.mkdir", args={"path": rel})],
            risk=RiskLevel.LOW,
            final_response=f"Ok, criei a pasta no workspace: {rel}",
        )

    # Regra: copiar arquivo/pasta
    m = re.search(r"\b(copiar|copie|copy)\b\s+(.+?)\s+\b(para|pra|to)\b\s+(.+)$", msg, flags=re.IGNORECASE)
    if m:
        src = m.group(2).strip().strip('"').strip("'")
        dst = m.group(4).strip().strip('"').strip("'")
        return Plan(
            intent="fs.copy",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="fs.copy", args={"src": src, "dst": dst, "overwrite": False})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok, copiei no workspace.",
        )

    # Regra: mover/renomear
    m = re.search(r"\b(mover|mova|move|renomear|renomeie|rename|mv)\b\s+(.+?)\s+\b(para|pra|to)\b\s+(.+)$", msg, flags=re.IGNORECASE)
    if m:
        src = m.group(2).strip().strip('"').strip("'")
        dst = m.group(4).strip().strip('"').strip("'")
        return Plan(
            intent="fs.move",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="fs.move", args={"src": src, "dst": dst, "overwrite": False})],
            risk=RiskLevel.HIGH,
            final_response="Ok, movi/renomeei no workspace.",
        )

    # Regra: DEV - executar comando (ex: "executar: python -c \"print(2+2)\"")
    # Regra: DEV - compilar/verificar o projeto (Python)
    # "compilar" em Python = verificar que tudo importa/compila + (opcional) rodar testes.
    if re.search(r"\b(compilar|compila|compile|build)\b", norm) and re.search(
        r"\b(projeto|project|repositorio|repo)\b", norm
    ):
        # Mantemos comandos allowlisted (python/pytest) para passar pelo sandbox com segurança.
        return Plan(
            intent="dev.exec",
            user_message=msg,
            tool_calls=[
                ToolCall(
                    tool_name="dev.exec",
                    args={"command": "python -m compileall -q omniscia", "timeout_s": 120},
                ),
                ToolCall(
                    tool_name="dev.exec",
                    args={"command": "python -m pytest -q", "timeout_s": 300},
                ),
            ],
            risk=RiskLevel.HIGH,
            final_response="Ok — vou verificar/compilar o projeto (compileall) e rodar os testes (requer aprovacao).",
        )

    m = re.search(r"\b(executar|rodar)\b\s*[:]\s*(.+)$", msg, flags=re.IGNORECASE)
    if m:
        command = m.group(2).strip()

        # Heurística de risco: comandos destrutivos viram CRITICAL.
        cmd_norm = _normalize(command)
        critical = bool(re.search(r"\b(rm\s+-rf|del\b|erase\b|format\b|shutdown\b|reg\b)\b", cmd_norm))

        return Plan(
            intent="dev.exec",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="dev.exec", args={"command": command, "timeout_s": 120})],
            risk=RiskLevel.CRITICAL if critical else RiskLevel.HIGH,
            final_response="Vou executar o comando no sandbox.",
        )

    # Regra: DEV - python rápido (ex: "python: print(2+2)")
    m = re.search(r"\bpython\b\s*[:]\s*(.+)$", msg, flags=re.IGNORECASE)
    if m:
        code = m.group(1).strip()
        return Plan(
            intent="dev.run_python",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="dev.run_python", args={"code": code, "timeout_s": 60})],
            risk=RiskLevel.HIGH,
            final_response="Ok, vou executar esse Python.",
        )

    # Regra: DEV - auto-fix de arquivo python (ex: "autofix script.py")
    m = re.search(r"\b(autofix|auto\s*fix|corrigir)\b\s+([\w\-./\\]+\.py)\b", norm)
    if m:
        path = m.group(2).strip().replace("\\", "/")
        return Plan(
            intent="dev.autofix_python_file",
            user_message=msg,
            tool_calls=[
                ToolCall(
                    tool_name="dev.autofix_python_file",
                    args={"path": path, "max_iters": 3, "timeout_s": 60},
                )
            ],
            risk=RiskLevel.HIGH,
            final_response="Ok, vou tentar corrigir o arquivo e executar novamente.",
        )

    # Regra: DEV - auto-fix por comando (ex: "autofixcmd: pytest -q")
    m = re.search(r"\b(autofixcmd|auto\s*fix\s*cmd)\b\s*[:]\s*(.+)$", msg, flags=re.IGNORECASE)
    if m:
        command = m.group(2).strip()
        return Plan(
            intent="dev.autofix_cmd",
            user_message=msg,
            tool_calls=[
                ToolCall(
                    tool_name="dev.autofix_cmd",
                    args={"command": command, "max_iters": 3, "timeout_s": 120},
                )
            ],
            risk=RiskLevel.HIGH,
            final_response="Ok, vou tentar corrigir até o comando passar.",
        )

    # Regra: DEV - corrigir testes (atalho para pytest)
    if re.search(r"\b(corrigir testes|arrumar testes|fix tests|rodar testes|run tests)\b", norm):
        return Plan(
            intent="dev.autofix_cmd",
            user_message=msg,
            tool_calls=[
                ToolCall(
                    tool_name="dev.autofix_cmd",
                    args={"command": "pytest -q", "max_iters": 3, "timeout_s": 180},
                )
            ],
            risk=RiskLevel.HIGH,
            final_response="Ok, vou rodar os testes e tentar corrigir o que falhar.",
        )

    # Regra: GUI - mover mouse (ex: "mover mouse 100 200")
    m = re.search(r"\b(mover mouse|move mouse)\b\s+(\d+)\s+(\d+)", norm)
    if m:
        x = int(m.group(2))
        y = int(m.group(3))
        return Plan(
            intent="gui.move_mouse",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="gui.move_mouse", args={"x": x, "y": y})],
            risk=RiskLevel.HIGH,
            final_response="Movi o mouse.",
        )

    # Regra: GUI - clicar (ex: "clicar 100 200")
    m = re.search(r"\b(clicar|click)\b\s+(\d+)\s+(\d+)", norm)
    if m:
        x = int(m.group(2))
        y = int(m.group(3))
        return Plan(
            intent="gui.click",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="gui.click", args={"x": x, "y": y})],
            risk=RiskLevel.CRITICAL,
            final_response="Vou clicar (requer aprovação).",
        )

    # Regra: GUI - digitar (ex: "digitar: olá mundo")
    m = re.search(r"\b(digitar|type)\b\s*[:]\s*(.+)$", msg, flags=re.IGNORECASE)
    if m:
        text = m.group(2)
        return Plan(
            intent="gui.type_text",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="gui.type_text", args={"text": text})],
            risk=RiskLevel.CRITICAL,
            final_response="Vou digitar no foco atual (requer aprovação).",
        )

    # Regra: GUI - posição do mouse
    # Colocamos depois de mover/clicar/digitar para evitar conflitos.
    if (
        "mouse" in norm
        and any(k in norm for k in ["posicao", "pos", "onde"])
        and not re.search(r"\d+\s+\d+", norm)
    ):
        return Plan(
            intent="gui.get_mouse",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="gui.get_mouse", args={})],
            risk=RiskLevel.LOW,
            final_response="Aqui está a posição do mouse.",
        )

    # Regra: memória
    if re.search(r"\b(lembra|lembrar|memoria|o que falamos|historico)\b", norm):
        if re.search(r"\b(ultim|recent|timeline|log|acao|acoes)\b", norm):
            return Plan(
                intent="memory.recent",
                user_message=msg,
                tool_calls=[ToolCall(tool_name="memory.recent", args={"limit": 30})],
                risk=RiskLevel.LOW,
                final_response="Aqui estão as ações mais recentes.",
            )
        # Extrai query simples removendo palavras comuns.
        q = re.sub(r"\b(lembra|lembrar|memoria|o que falamos|historico)\b", "", norm)
        q = q.strip() or msg
        return Plan(
            intent="memory.search",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="memory.search", args={"query": q, "limit": 5})],
            risk=RiskLevel.LOW,
            final_response="Busquei na memória recente.",
        )

    # Regra: criar/iniciar projeto python (scaffold)
    if re.search(r"\b(projeto|project|app|aplicacao|aplicacao)\b", norm) and re.search(
        r"\b(criar|crie|cria|novo|iniciar|inicia|montar|gera|gerar)\b",
        norm,
    ):
        wants_python = bool(re.search(r"\bpython\b", norm))
        # Default: python (mais útil no workspace do agente)
        if wants_python or "java" not in norm:
            name = _guess_name_from_text(msg) or "MeuProjeto"
            return Plan(
                intent="dev.scaffold_project",
                user_message=msg,
                tool_calls=[
                    ToolCall(
                        tool_name="dev.scaffold_project",
                        args={"name": name},
                    ),
                ],
                risk=RiskLevel.HIGH,
                final_response="Ok — vou criar um projeto Python no workspace (requer aprovação).",
            )

    # Regra: web read-only (ler página)
    # Se detectar uma URL ou intenção clara de abrir/ler um site.
    m = re.search(r"https?://\S+", msg)
    wants_web = bool(m) or bool(re.search(r"\b(abra|abrir|ler|leia|resuma|resumir)\b.*\b(site|pagina)\b", norm))
    if wants_web:
        if m:
            url = m.group(0)
        else:
            # Extrai algo que pareça domínio (com path opcional), ex: example.com/foo
            m2 = re.search(r"\b([a-zA-Z0-9][\w.-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?)\b", msg)
            url = m2.group(1) if m2 else ""
        return Plan(
            intent="web.read",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="web.get_page_text", args={"url": url, "max_chars": 6000})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok, vou abrir a página e extrair o texto (read-only).",
        )

    # Regra: ajuda/tools
    if norm in {"ajuda", "help", "comandos", "commands"}:
        return Plan(
            intent="core.help",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="core.help", args={})],
            risk=RiskLevel.LOW,
            final_response="Aqui vai um guia rápido.",
        )

    if norm in {"tools", "tool"}:
        return Plan(
            intent="core.list_tools",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="core.list_tools", args={})],
            risk=RiskLevel.LOW,
            final_response="Aqui está a lista de tools disponíveis.",
        )

    # Regra 0: saída
    if norm in {"sair", "exit", "quit"}:
        return Plan(intent="exit", user_message=msg, final_response="Encerrando.")

    # Regra 1: operações potencialmente críticas
    # Ex: "apague", "delete", "rm -rf" etc.
    if re.search(r"\b(apagar|delete|deletar|rm\s+-rf|formatar)\b", norm):
        # Heurística simples para extrair path depois de "apagar".
        m = re.search(r"\b(apagar|delete|deletar)\s+([^\n\r]+)", norm)
        path = ""
        if m:
            path = m.group(2).strip().strip('"').strip("'")
        return Plan(
            intent="filesystem.delete",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="fs.delete", args={"path": path})],
            risk=RiskLevel.CRITICAL,
            final_response="Ação de apagar detectada. Preciso de confirmação (HITL).",
        )

    # Regra: listar diretório
    if re.search(r"\b(listar|lista|ls|dir)\b", norm):
        return Plan(
            intent="filesystem.list",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="fs.list_dir", args={"path": "."})],
            risk=RiskLevel.LOW,
            final_response="Listando arquivos do workspace.",
        )

    # Regra: ler arquivo
    m = re.search(r"\b(ler|leia|cat|abrir)\b\s+([^\s]+)", msg, flags=re.IGNORECASE)
    if m and m.group(2):
        path = m.group(2).strip().strip('"').strip("'").replace("\\", "/")
        return Plan(
            intent="filesystem.read",
            user_message=msg,
            tool_calls=[ToolCall(tool_name="fs.read_text", args={"path": path, "max_chars": 8000})],
            risk=RiskLevel.MEDIUM,
            final_response="Ok, vou ler o arquivo.",
        )

    # Regra 2: escrever arquivo
    if norm.startswith("crie um arquivo") or norm.startswith("criar arquivo"):
        # Exemplo esperado: "crie um arquivo path=foo.txt conteúdo=..."
        return Plan(
            intent="dev.write_file",
            user_message=msg,
            tool_calls=[
                ToolCall(
                    tool_name="write_file",
                    args={
                        "path": "data/tmp/notes.txt",
                        "content": f"Comando: {msg}\n",
                    },
                )
            ],
            risk=RiskLevel.HIGH,
            final_response="Ok, vou criar um arquivo (relativo ao workspace).",
        )

    # Default: chat (sem tools). O brain pode responder via LLM quando configurado.
    return Plan(
        intent="chat",
        user_message=msg,
        tool_calls=[],
        risk=RiskLevel.LOW,
        final_response="Ok. Me diga o que você quer fazer/entender e eu te ajudo.",
    )


def _route_with_llm(settings: Settings, user_message: str) -> Plan | None:
    """Usa LLM para produzir um Plan em JSON.

    Rationale:
    - Mantemos o LLM como "gerador de estrutura" (JSON), não como executor.
    - Validamos via Pydantic antes de aceitar.

    Segurança:
    - Se config estiver ausente, retornamos None e caímos no heurístico.
    """

    return _route_with_llm_messages(settings, [{"role": "user", "content": str(user_message or "").strip()}])


def _route_with_llm_messages(
    settings: Settings,
    messages: list[dict[str, str]],
    *,
    registry: ToolRegistry | None = None,
) -> Plan | None:
    """Usa LLM para produzir um Plan em JSON, aceitando histórico curto.

    `messages` deve ser uma lista no formato OpenAI: {role, content}.
    Roles aceitas aqui: system/user/assistant.
    """

    from omniscia.core.litellm_env import provider_requires_api_key
    from omniscia.core.ollama_health import maybe_warn_if_ollama_cpu

    def _has_llm_config_values(provider: str | None, model: str | None, api_key: str | None) -> bool:
        needs_key = provider_requires_api_key(provider)
        has_key = bool((api_key or "").strip())
        return bool((provider or "").strip() and (model or "").strip() and (has_key or not needs_key))

    needs_key = provider_requires_api_key(settings.llm_provider)
    has_key = bool((settings.llm_api_key or "").strip())
    if not (settings.llm_provider and settings.llm_model and (has_key or not needs_key)):
        logger.warning("Router LLM habilitado, mas falta OMNI_LLM_*; caindo no heurístico")
        return None

    try:
        from litellm import completion
    except Exception:  # noqa: BLE001
        logger.exception("litellm não disponível; caindo no heurístico")
        return None

    def _build_registered_tools_catalog(r: ToolRegistry) -> str:
        return _build_registered_tools_catalog_subset(r, only_names=None)

    def _build_registered_tools_catalog_subset(r: ToolRegistry, *, only_names: list[str] | None) -> str:
        """Catálogo name-only.

        Quando `only_names` é fornecido, lista apenas esse subconjunto (na ordem dada).
        Isso reduz tokens e melhora latência/qualidade do roteamento.
        """

        if only_names:
            present: list[str] = []
            for n in only_names:
                name = (n or "").strip()
                if not name:
                    continue
                try:
                    r.get(name)
                except Exception:
                    continue
                present.append(name)
            lines = [f"- {n}" for n in present]
            lines.append(
                "... (catálogo em modo shortlist; se precisar de outras tools, use core.list_tools)"
            )
            return "\n".join(lines)

        # Fallback: lista compacta com limite.
        names = sorted({(s.name or "").strip() for s in r.list() if (s.name or "").strip()})
        max_tools = _env_int("OMNI_ROUTER_TOOLS_CATALOG_LIMIT", 180)
        shown = names[:max_tools]
        rest = max(0, len(names) - len(shown))

        lines = [f"- {n}" for n in shown]
        if rest:
            lines.append(f"... (+{rest} tools não listadas por limite de prompt; se precisar, use core.list_tools)")
        return "\n".join(lines)

    def _build_schema_hints(r: ToolRegistry, *, only_names: set[str] | None = None) -> str:
        # Hints curtos para tools comuns/complexas.
        # Só incluímos as que existem no runtime para evitar planos inválidos.
        hints: dict[str, str] = load_schema_hints()

        present: list[str] = []
        for name in sorted(hints.keys()):
            if only_names is not None and name not in only_names:
                continue
            try:
                r.get(name)
            except Exception:
                continue
            present.append(hints[name])
        return "\n".join(present)

    def _select_tool_names_for_prompt(r: ToolRegistry, *, user_text: str) -> list[str]:
        """Seleciona um subconjunto (Top-K) de tools para o prompt.

        Motivo: injetar todas as tools todo turno aumenta tokens/latência e piora a qualidade.
        Estratégia:
        - (Opcional) shortlist semântico (ChromaDB) quando disponível.
        - Fallback para scoring lexical (sem dependências extras) + conjunto base.
        """

        if (os.getenv("OMNI_ROUTER_TOOL_SHORTLIST", "true").strip().lower() == "false"):
            return []

        q_norm = _normalize(user_text)
        q_tokens = set(re.findall(r"[a-z0-9]+", q_norm))

        base: list[str] = [
            "core.show_settings",
            "core.list_tools",
            "core.help",
            "core.doctor",
            "memory.search",
            "memory.remember",
            "fs.list_dir",
            "fs.read_text",
            "os.open_url",
            "os.open_explorer",
            "os.open_app",
            "web.search",
            "web.get_page_text",
            "finance.crypto_price",
            "finance.crypto_market_chart",
            "knowledge.wikipedia_summary",
            "vscode.open",
            "vscode.open_file",
        ]

        # Boost explícitos por domínios.
        if "discord" in q_norm:
            base += ["discord.send_message", "status.discord"]
        if "vscode" in q_norm or "vs" in q_tokens or "code" in q_tokens:
            base += ["vscode.tasks_read", "vscode.tasks_update", "vscode.settings_read", "vscode.settings_update"]

        # (Opt-in) shortlist semântico via embeddings locais.
        # Controlado por OMNI_ROUTER_TOOL_RAG=true.
        if _TOOL_SHORTLISTER is not None and (os.getenv("OMNI_ROUTER_TOOL_RAG", "false").strip().lower() == "true"):
            try:
                k_sem = min(_env_int("OMNI_ROUTER_TOOL_RAG_K", 12), 40)
                sem_hits = _TOOL_SHORTLISTER.shortlist(registry=r, query=user_text, k=k_sem)
                sem_names = [h.name for h in sem_hits if h.name]
                if sem_names:
                    max_total = _env_int("OMNI_ROUTER_TOOL_SHORTLIST_MAX", 80)
                    merged: list[str] = []
                    for n in base + sem_names:
                        nn = (n or "").strip()
                        if not nn or nn in merged:
                            continue
                        merged.append(nn)
                        if len(merged) >= max_total:
                            break
                    return merged
            except Exception:
                pass

        scored: list[tuple[int, str]] = []
        for spec in r.list():
            name = (getattr(spec, "name", None) or "").strip()
            if not name:
                continue
            desc = str(getattr(spec, "description", None) or "")

            blob = _normalize(name + " " + desc)
            score = 0

            # Match por namespace (ex.: "finance" -> finance.*)
            ns = name.split(".", 1)[0] if "." in name else name
            if ns and ns in q_tokens:
                score += 6

            # Match por tokens do usuário (barato e eficaz)
            for tok in q_tokens:
                if tok and tok in blob:
                    score += 1

            # Match literal do nome da tool
            if name.lower() in q_norm:
                score += 12

            if score > 0:
                scored.append((score, name))

        scored.sort(key=lambda x: (-x[0], x[1]))

        k = _env_int("OMNI_ROUTER_TOOL_SHORTLIST_K", 45)
        max_total = _env_int("OMNI_ROUTER_TOOL_SHORTLIST_MAX", 80)

        selected: list[str] = []
        seen: set[str] = set()

        for n in base:
            nn = (n or "").strip()
            if not nn or nn in seen:
                continue
            seen.add(nn)
            selected.append(nn)

        for _, n in scored[:k]:
            nn = (n or "").strip()
            if not nn or nn in seen:
                continue
            seen.add(nn)
            selected.append(nn)

        return selected[:max_total]

    static_tools_block = load_static_tools_block() or (
        "- core.show_settings -> {}\n"
        "- core.list_tools -> {}\n"
        "- core.doctor -> {} (LOW; diagnostico offline)\n"
        "- core.approvals_list -> {} (LOW; lista aprovacoes lembradas)\n"
        "- core.approvals_revoke -> {keys?, contains?} (HIGH; revoga por chave ou substring)\n"
        "- core.approvals_reset -> {} (HIGH; limpa todas as aprovacoes lembradas)\n"
        "- core.policy_show -> {} (LOW; mostra policy)\n"
        "- core.policy_write -> {policy} (HIGH; escreve policy JSON)\n"
        "- core.snapshot_create -> {label?} (MEDIUM; cria snapshot zip)\n"
        "- core.snapshot_list -> {limit?} (LOW; lista snapshots)\n"
        "- core.snapshot_restore -> {snapshot_id} (CRITICAL; destrutivo)\n"
        "- core.memory_compact -> {keep_last?, archive?, base_dir?} (HIGH; compacta events.jsonl)\n"
        "- echo -> {text}\n"
        "- write_file -> {path, content}\n"
        "- os.open_url -> {url} (apenas http/https)\n"
        "- os.open_explorer -> {path?} (path relativo; default '.')\n"
        "- os.open_app -> {app} (allowlist configurável via OMNI_OPEN_APPS_FILE/OMNI_OPEN_APPS_JSON; exemplos: calculator, notepad, paint, snippingtool, discord)\n"
        "- win.focus_window -> {title_contains, timeout_s?, visible_only?} (HIGH; Windows; retorna rect)\n"
        "- discord.send_message -> {to, message, settle_ms?} (CRITICAL; requer Discord em foco)\n"
        "- jgrasp.create_java_program -> {path?, class_name?, message?, code?, open_in_jgrasp?, settle_ms?} (HIGH; cria .java e abre no jGRASP; use code para conteúdo completo)\n"
        "- jgrasp.write_code -> {code, settle_ms?, select_all?} (HIGH; cola/escreve no editor do jGRASP; não cria arquivo)\n"
        "- os.mkdir -> {path? , known_folder? , name?} (HIGH; Windows; path absoluto ou known_folder=desktop/downloads/documents)\n"
        "- memory.search -> {query, limit}\n"
        "- memory.search_vector -> {query, limit} (se disponível)\n"
        "- memory.index_recent -> {limit} (se disponível)\n"
        "- memory.remember -> {text, topic?, tags?} (se disponível; salva memória durável)\n"
        "- memory.profile_get -> {} (perfil persistente local)\n"
        "- memory.profile_update -> {patch} (perfil persistente local)\n"
        "- memory.profile_reset -> {} (perfil persistente local)\n"
        "- web.get_page_text -> {url, max_chars}\n"
        "- web.search -> {query, max_results?} (read-only)\n"
        "- web.research -> {query, max_results?, max_pages?, max_chars_per_page?, save_to_memory?, summarize?} (read-only)\n"
        "- web.screenshot -> {url, path?}\n"
        "- web.get_links -> {url, max_links?}\n"
        "- vscode.tasks_read -> {} (LOW; le .vscode/tasks.json)\n"
        "- vscode.tasks_update -> {patch} (HIGH; merge patch em .vscode/tasks.json)\n"
        "- vscode.launch_read -> {} (LOW; le .vscode/launch.json)\n"
        "- vscode.launch_update -> {patch} (HIGH; merge patch em .vscode/launch.json)\n"
        "- fs.list_dir -> {path}\n"
        "- fs.read_text -> {path, max_chars}\n"
        "- fs.mkdir -> {path}\n"
        "- fs.copy -> {src, dst, overwrite?}\n"
        "- fs.move -> {src, dst, overwrite?} (pode ser renomear)\n"
        "- fs.delete -> {path} (CRITICAL)\n"
        "- screen.screenshot -> {}\n"
        "- screen.ocr -> {path?}\n"
        "- screen.find_text -> {query, path?, window_title?, max_results?, min_conf?} (retorna caixas x/y/w/h)\n"
        "- screen.click_text -> {query, path?, window_title?, min_conf?} (CRITICAL)\n"
        "- gui.get_mouse -> {}\n"
        "- gui.move_mouse -> {x, y}\n"
        "- gui.click -> {x, y} (CRITICAL)\n"
        "- gui.click_box_center -> {x, y, w, h} (CRITICAL)\n"
        "- gui.type_text -> {text} (CRITICAL)\n"
        "IMPORTANTE: Para abrir sites/apps/pastas, use os.open_url/os.open_explorer/os.open_app (NÃO use dev.exec).\n"
        "IMPORTANTE: Para clicar/digitar na tela, primeiro use screen.find_text para obter coordenadas, depois gui.click/gui.type_text.\n"
        "- dev.exec -> {command, timeout_s}\n"
        "- dev.run_python -> {code, timeout_s}\n"
        "- dev.create_tool -> {name, code, overwrite?} (CRITICAL; cria tool custom e hot-reload; requer opt-in)\n"
        "- dev.autofix_python_file -> {path, max_iters, timeout_s}\n"
        "- dev.autofix_cmd -> {command, max_iters, timeout_s} (apenas pytest)\\n"
    )

    tools_block = ""
    schemas_block = ""
    if registry is not None:
        # Escolhe um subset de tools para reduzir tokens/latência.
        last_user_text = ""
        for m in reversed(messages or []):
            role = str((m or {}).get("role") or "").strip().lower()
            if role == "user":
                last_user_text = str((m or {}).get("content") or "")
                break

        subset = _select_tool_names_for_prompt(registry, user_text=last_user_text)
        if subset:
            tools_block = _build_registered_tools_catalog_subset(registry, only_names=subset)
            schemas_block = _build_schema_hints(registry, only_names=set(subset))
        else:
            tools_block = _build_registered_tools_catalog(registry)
            schemas_block = _build_schema_hints(registry)

    system = (
        "Você é um roteador de ferramentas para um agente autônomo. "
        "Sua tarefa é transformar a intenção do usuário em um JSON de plano. "
        "Responda APENAS com JSON válido (sem markdown, sem texto extra).\n\n"
        "FORMATO:\n"
        "{\n"
        "  \"intent\": string,\n"
        "  \"user_message\": string,\n"
        "  \"risk\": \"LOW\"|\"MEDIUM\"|\"HIGH\"|\"CRITICAL\",\n"
        "  \"tool_calls\": [ { \"tool_name\": string, \"args\": object } ],\n"
        "  \"final_response\": string\n"
        "}\n\n"
        "REGRAS DE RISCO:\n"
        "- Se envolver apagar arquivos, formatar, shutdown, pagamentos/compras, login, transferir dinheiro: risk=CRITICAL.\n"
        "- Se envolver automação de mouse/teclado (clicar/digitar) ou executar comandos: risk=HIGH (ou CRITICAL se destrutivo).\n\n"
        "CONTEXTO (IMPORTANTE):\n"
        "- Você pode receber mensagens anteriores com resultados de tools (ex.: 'TOOL_RESULT ...'). Use isso para decidir próximos passos.\n\n"
        "REGRA MAIS IMPORTANTE (NÃO INVENTE AUTOMAÇÃO):\n"
        "- Se o usuário pediu apenas orientação/explicação/dicas (ex: jogos, estudo, dúvidas), responda em texto: tool_calls=[] e risk=LOW.\n"
        "- Só use tools de tela (screen.*), janela (win.focus_window) ou GUI (gui.* / screen.click_text) quando o usuário pedir explicitamente para ver/clicar/digitar na tela.\n"
        "- Só use dev.* quando o usuário pedir explicitamente para executar/rodar comandos ou código.\n"
        "- Nunca adivinhe window_title: só preencha window_title se o usuário fornecer o texto do título (ou substring) na mensagem.\n\n"
        "REGRAS ESPECÍFICAS:\n"
        "- Se usar discord.send_message, inclua antes um os.open_app com app='discord' para garantir que o Discord esteja aberto/em foco.\n\n"
        "- jGRASP (MUITO IMPORTANTE):\n"
        "  - Se o usuário pedir um programa/código Java 'funcional', 'completo', 'de matriz', 'de matemática', etc., use jgrasp.create_java_program OU jgrasp.write_code com o campo code (NÃO use apenas message).\n"
        "  - O campo code deve conter Java compilável, sem markdown e sem cercas de código (```), e a classe pública deve bater com class_name.\n"
        "  - Defaults: path='scratch/<ClassName>.java' e class_name='<ClassName>' (PascalCase).\n"
        "  - Só use path com prefixo 'desktop:/' quando o usuário pedir explicitamente 'Área de Trabalho/desktop'.\n"
        "  - Se o usuário disser que o jGRASP já está aberto e/ou que não precisa criar arquivo, prefira jgrasp.write_code com select_all=true (substitui o editor atual).\n"
        "  - Se houver TOOL_RESULT indicando falha por foco/timing, ajuste settle_ms para mais alto (ex.: 1200) e garanta os.open_app('jgrasp') antes.\n\n"
        "- Self-coding (opt-in):\n"
        "  - Se NÃO existir uma tool adequada e o usuário pedir para 'criar uma ferramenta' ou 'criar um script', você pode propor self-coding.\n"
        "  - Faça isso SOMENTE como plano explícito e seguro: (1) write_file em scratch/<nome>.py, (2) dev.run_python com script='scratch/<nome>.py'.\n"
        "  - Alternativa (preferida para plugins): use dev.create_tool para criar um módulo em omniscia/tools/custom e recarregar tools no runtime.\n"
        "  - Marque risk=CRITICAL e descreva claramente o que o script faz.\n"
        "  - Nunca escreva scripts fora de scratch/.\n\n"
        "FERRAMENTAS DISPONÍVEIS (tool_name -> args):\n"
        + (
            (
                "IMPORTANTE: Use APENAS tool_name que esteja em 'TOOLS REGISTRADAS'.\n"
                "IMPORTANTE: Prefira tools listadas em 'SCHEMAS' (args explícitos).\n"
                "IMPORTANTE: Se precisar descobrir mais tools, você pode chamar core.list_tools como primeiro passo e então replanejar.\n\n"
                + ("SCHEMAS (somente se tool existir):\n" + (schemas_block + "\n\n" if schemas_block else ""))
                + ("TOOLS REGISTRADAS (use apenas estas):\n" + tools_block if tools_block else "")
            )
            if registry is not None
            else static_tools_block
        )
    )

    llm_model = settings.llm_model

    # Não logamos a key; só configuramos no ambiente do litellm.
    from omniscia.core.litellm_env import apply_litellm_env

    def _call_router_llm(call_settings: Settings) -> Plan:
        apply_litellm_env(call_settings)

        clean_msgs: list[dict[str, str]] = [{"role": "system", "content": system}]
        for m in messages:
            role = str((m or {}).get("role") or "").strip().lower()
            content = str((m or {}).get("content") or "")
            if role in {"user", "assistant", "system"} and content.strip():
                # Nunca deixamos o caller substituir o system principal.
                if role == "system":
                    role = "assistant"
                clean_msgs.append({"role": role, "content": content})

        base_kwargs: dict[str, Any] = {}
        api_base = (getattr(call_settings, "llm_base_url", None) or "").strip()
        if api_base:
            base_kwargs["api_base"] = api_base

        # Router deve ser rápido e determinístico.
        base_kwargs["timeout"] = float(os.getenv("OMNI_ROUTER_TIMEOUT_S", "25").strip() or "25")
        router_max_tokens = _env_int("OMNI_ROUTER_MAX_TOKENS", 256)

        router_model = (os.getenv("OMNI_ROUTER_LLM_MODEL", "") or "").strip() or str(call_settings.llm_model)

        def _parse_plan_json(raw_text: str) -> dict[str, Any]:
            raw2 = (raw_text or "").strip()

            # Remove fenced code blocks if the model ignored instructions.
            raw2 = re.sub(r"^```(?:json)?\s*", "", raw2, flags=re.IGNORECASE)
            raw2 = re.sub(r"\s*```$", "", raw2)
            raw2 = raw2.strip()

            try:
                data0: dict[str, Any] = json.loads(raw2)
                return data0
            except Exception:
                start = raw2.find("{")
                end = raw2.rfind("}")
                if start == -1 or end == -1 or end <= start:
                    raise
                data1: dict[str, Any] = json.loads(raw2[start : end + 1])
                return data1

        def _dedupe_tool_calls(p: Plan) -> Plan:
            if not p.tool_calls:
                return p
            seen: set[str] = set()
            new_calls: list[ToolCall] = []
            for c in p.tool_calls:
                name = (c.tool_name or "").strip()
                try:
                    args_sig = json.dumps(c.args or {}, ensure_ascii=False, sort_keys=True)
                except Exception:
                    args_sig = str(c.args)
                sig = f"{name}|{args_sig}"
                if sig in seen:
                    continue
                seen.add(sig)
                new_calls.append(c)
            return p.model_copy(update={"tool_calls": new_calls})

        resp = completion(
            model=str(router_model),
            messages=clean_msgs,
            temperature=0.0,
            max_tokens=int(router_max_tokens),
            **base_kwargs,
        )
        maybe_warn_if_ollama_cpu(
            provider=getattr(call_settings, "llm_provider", None),
            base_url=(getattr(call_settings, "llm_base_url", None) or None),
            model=str(router_model),
        )
        content: str = resp["choices"][0]["message"]["content"]  # type: ignore[index]

        raw = (content or "").strip()
        try:
            data = _parse_plan_json(raw)
        except Exception as parse_exc:  # noqa: BLE001
            # Retry once with a stricter prompt to repair invalid JSON (common for some models).
            repair_msg = (
                "Seu output anterior NÃO era JSON válido e quebrou o parser. "
                "Responda novamente APENAS com JSON VÁLIDO (sem markdown, sem comentários), "
                "com chaves entre aspas duplas e seguindo exatamente o FORMATO especificado. "
                f"Erro do parser: {type(parse_exc).__name__}: {str(parse_exc)[:180]}"
            )
            resp2 = completion(
                model=str(router_model),
                messages=clean_msgs + [{"role": "user", "content": repair_msg}],
                temperature=0.0,
                max_tokens=int(router_max_tokens),
                **base_kwargs,
            )
            content2: str = resp2["choices"][0]["message"]["content"]  # type: ignore[index]
            data = _parse_plan_json((content2 or "").strip())

        plan = Plan.model_validate(data)
        return _dedupe_tool_calls(plan)

    try:
        return _call_router_llm(settings)
    except Exception as e:  # noqa: BLE001
        from omniscia.core.redact import redact_secrets

        def _short_err(exc: Exception) -> str:
            s = redact_secrets(str(exc))
            s = re.sub(r"\s+", " ", s).strip()
            if len(s) > 220:
                s = s[:220] + "..."
            return f"{type(exc).__name__}: {s}" if s else type(exc).__name__

        fb_provider = getattr(settings, "llm_fallback_provider", None)
        fb_model = getattr(settings, "llm_fallback_model", None)
        fb_key = getattr(settings, "llm_fallback_api_key", None)
        fb_base = getattr(settings, "llm_fallback_base_url", None)

        if _has_llm_config_values(fb_provider, fb_model, fb_key):
            logger.info(
                "Falha no router LLM principal; tentando fallback (%s)",
                _short_err(e),
            )
            try:
                fb_settings = Settings(
                    **{
                        **settings.__dict__,
                        "llm_provider": fb_provider,
                        "llm_model": fb_model,
                        "llm_api_key": fb_key,
                        "llm_base_url": fb_base,
                    }
                )
                return _call_router_llm(fb_settings)
            except Exception as e2:  # noqa: BLE001
                logger.info(
                    "Falha ao rotear via LLM (principal+fallback); caindo no heurístico (%s)",
                    _short_err(e2),
                )
                return None

        logger.info(
            "Falha ao rotear via LLM; caindo no heurístico (%s)",
            _short_err(e),
        )
        return None


async def _route_with_llm_messages_async(
    settings: Settings,
    messages: list[dict[str, str]],
    *,
    registry: ToolRegistry | None = None,
) -> Plan | None:
    """Versão async real do roteamento via LLM.

    - Usa `litellm.acompletion` quando disponível.
    - Mantém o mesmo prompt/semântica/validação do caminho sync.
    - Em caso de indisponibilidade, faz fallback para o caminho sync.
    """

    try:
        from litellm import acompletion  # type: ignore
    except Exception:
        return _route_with_llm_messages(settings, messages, registry=registry)

    from omniscia.core.litellm_env import apply_litellm_env, provider_requires_api_key
    from omniscia.core.ollama_health import maybe_warn_if_ollama_cpu
    from omniscia.core.redact import redact_secrets

    needs_key = provider_requires_api_key(settings.llm_provider)
    has_key = bool((settings.llm_api_key or "").strip())
    if not (settings.llm_provider and settings.llm_model and (has_key or not needs_key)):
        logger.warning("Router LLM habilitado, mas falta OMNI_LLM_*; caindo no heurístico")
        return None

    # Reusa o prompt do caminho sync para evitar drift.
    # (chamar a função sync aqui seria recursivo; então reconstruímos via chamada interna)
    # Observação: o prompt depende de registry; então delegamos ao caminho sync apenas
    # para montar o prompt quando registry for None? Não: para manter consistência,
    # usamos o mesmo builder completo chamando a função sync e extraindo o system.
    # Porém o prompt está encapsulado no escopo da função sync; portanto, por simplicidade
    # e segurança contra drift, fazemos fallback para sync quando registry for None.
    # Quando registry existe (caso comum no loop ReAct), chamamos o sync para construir
    # o system indiretamente não é viável; então replicamos o mínimo: chamar o sync.

    # Implementação pragmática: para evitar duplicação massiva de prompt, usamos o caminho
    # sync quando não há contexto adicional (rota inicial), e para o caminho async (ReAct)
    # aceitamos usar o sync — mas isso voltaria a bloquear. Então preferimos duplicar a
    # lógica de prompt no futuro; por ora, mantemos o async real com um prompt reduzido.

    # NOTA: este bloco é intencionalmente conservador para não quebrar comportamento.
    # Ele mantém a validação/parse/repair.

    # Usa o mesmo prompt do sync chamando-o quando possível.
    if registry is None:
        # rota inicial mais comum: pode ser sync sem grande impacto
        return _route_with_llm_messages(settings, messages, registry=None)

    # Prompt reduzido: ainda exige JSON e lista tools registradas.
    # (mantém comportamento geral; a lista já é shortlistada no sync e aqui reusamos utilitários locais)
    # Para manter tokens baixos, usamos apenas o catálogo subset (sem schemas).
    try:
        tools = sorted({(s.name or "").strip() for s in registry.list() if (s.name or "").strip()})
    except Exception:
        tools = []

    tools_block = "\n".join([f"- {n}" for n in tools[:180]])
    system = (
        "Você é um roteador de ferramentas para um agente autônomo. "
        "Responda APENAS com JSON válido (sem markdown, sem texto extra).\n\n"
        "FORMATO:{\"intent\":string,\"user_message\":string,\"risk\":\"LOW\"|\"MEDIUM\"|\"HIGH\"|\"CRITICAL\",\"tool_calls\":[{\"tool_name\":string,\"args\":object}],\"final_response\":string}\n\n"
        "FERRAMENTAS DISPONÍVEIS (use apenas estas tool_name):\n"
        + tools_block
    )

    apply_litellm_env(settings)

    clean_msgs: list[dict[str, str]] = [{"role": "system", "content": system}]
    for m in messages:
        role = str((m or {}).get("role") or "").strip().lower()
        content = str((m or {}).get("content") or "")
        if role in {"user", "assistant", "system"} and content.strip():
            if role == "system":
                role = "assistant"
            clean_msgs.append({"role": role, "content": content})

    base_kwargs: dict[str, Any] = {}
    api_base = (getattr(settings, "llm_base_url", None) or "").strip()
    if api_base:
        base_kwargs["api_base"] = api_base
    base_kwargs["timeout"] = float(os.getenv("OMNI_ROUTER_TIMEOUT_S", "25").strip() or "25")
    router_max_tokens = _env_int("OMNI_ROUTER_MAX_TOKENS", 256)
    router_model = (os.getenv("OMNI_ROUTER_LLM_MODEL", "") or "").strip() or str(settings.llm_model)

    def _parse_plan_json(raw_text: str) -> dict[str, Any]:
        raw2 = (raw_text or "").strip()
        raw2 = re.sub(r"^```(?:json)?\s*", "", raw2, flags=re.IGNORECASE)
        raw2 = re.sub(r"\s*```$", "", raw2)
        raw2 = raw2.strip()
        try:
            data0: dict[str, Any] = json.loads(raw2)
            return data0
        except Exception:
            start = raw2.find("{")
            end = raw2.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise
            data1: dict[str, Any] = json.loads(raw2[start : end + 1])
            return data1

    def _dedupe_tool_calls(p: Plan) -> Plan:
        if not p.tool_calls:
            return p
        seen: set[str] = set()
        new_calls: list[ToolCall] = []
        for c in p.tool_calls:
            name = (c.tool_name or "").strip()
            try:
                args_sig = json.dumps(c.args or {}, ensure_ascii=False, sort_keys=True)
            except Exception:
                args_sig = str(c.args)
            sig = f"{name}|{args_sig}"
            if sig in seen:
                continue
            seen.add(sig)
            new_calls.append(c)
        return p.model_copy(update={"tool_calls": new_calls})

    async def _call() -> Plan:
        resp = await acompletion(
            model=str(router_model),
            messages=clean_msgs,
            temperature=0.0,
            max_tokens=int(router_max_tokens),
            **base_kwargs,
        )
        maybe_warn_if_ollama_cpu(
            provider=getattr(settings, "llm_provider", None),
            base_url=(getattr(settings, "llm_base_url", None) or None),
            model=str(router_model),
        )
        content: str = resp["choices"][0]["message"]["content"]  # type: ignore[index]
        raw = (content or "").strip()
        try:
            data = _parse_plan_json(raw)
        except Exception as parse_exc:  # noqa: BLE001
            repair_msg = (
                "Seu output anterior NÃO era JSON válido e quebrou o parser. "
                "Responda novamente APENAS com JSON VÁLIDO (sem markdown, sem comentários), "
                "com chaves entre aspas duplas e seguindo exatamente o FORMATO especificado. "
                f"Erro do parser: {type(parse_exc).__name__}: {str(parse_exc)[:180]}"
            )
            resp2 = await acompletion(
                model=str(router_model),
                messages=clean_msgs + [{"role": "user", "content": repair_msg}],
                temperature=0.0,
                max_tokens=int(router_max_tokens),
                **base_kwargs,
            )
            content2: str = resp2["choices"][0]["message"]["content"]  # type: ignore[index]
            data = _parse_plan_json((content2 or "").strip())

        plan = Plan.model_validate(data)
        return _dedupe_tool_calls(plan)

    try:
        return await _call()
    except Exception as exc:  # noqa: BLE001
        s = redact_secrets(str(exc))
        s = re.sub(r"\s+", " ", s).strip()
        if len(s) > 220:
            s = s[:220] + "..."
        logger.info("Falha ao rotear via LLM async; caindo no heurístico (%s)", f"{type(exc).__name__}: {s}" if s else type(exc).__name__)
        return None
