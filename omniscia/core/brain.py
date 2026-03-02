"""O Cérebro (loop principal).

Responsabilidades:
- Receber input (MVP: texto; depois voz)
- Rotejar para um plano (heurístico ou LLM)
- Aplicar políticas (HITL)
- Executar ferramentas e retornar uma resposta final

Observação importante:
- Neste estágio, a interação é via terminal para manter o MVP simples e robusto.
- A voz (STT/TTS) entra como módulos plugáveis posteriormente.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from dataclasses import replace
from rich.console import Console
from rich.panel import Panel

from omniscia.core.config import Settings
from omniscia.core.hitl import require_approval
from omniscia.core.router import route
from omniscia.core.tools import build_default_registry
from omniscia.core.types import Plan, RiskLevel, ToolCall
from omniscia.core.wakeword import extract_after_wake_word
from omniscia.core.chat_llm import chat_reply
from omniscia.modules.stt.factory import build_stt
from omniscia.modules.tts.factory import build_tts
from omniscia.modules.memory.store import JsonlMemoryStore

logger = logging.getLogger(__name__)


def run_brain_loop(settings: Settings) -> None:
    """Loop REPL do agente."""

    console = Console()
    memory = JsonlMemoryStore()
    registry = build_default_registry(settings=settings, memory_store=memory)
    stt = build_stt(settings, console=console)
    tts = build_tts(settings, console=console)

    console.print(Panel.fit("Omnisciência (MVP) — digite seu comando (ou 'sair')", title="OK"))

    while True:
        try:
            if stt.is_voice:
                console.print(
                    f"\n[dim]Gravando por ~{settings.stt_record_seconds}s... fale agora.[/dim]"
                )
            user_message = stt.listen().strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nEncerrando.")
            return
        except Exception as exc:  # noqa: BLE001
            # Se o STT falhar (microfone, deps), caímos para texto no próximo loop.
            logger.exception("Falha no STT")
            console.print(f"[red]Erro no STT:[/red] {exc}")
            console.print("[yellow]Voltando para modo texto.[/yellow]")
            settings = replace(settings, stt_mode="text")
            stt = build_stt(settings, console=console)
            continue

        if not user_message:
            continue

        if stt.is_voice:
            # Transparência: mostra o texto transcrito antes de agir.
            console.print(f"[cyan]Você (voz)>[/cyan] {user_message}")

            # Wake word: só atende quando for chamado (ex: "ei void ...").
            if getattr(settings, "wake_word_enabled", False):
                ok, cmd = extract_after_wake_word(
                    user_message,
                    wake_word=getattr(settings, "wake_word", "void"),
                    mode=getattr(settings, "wake_word_mode", "prefix"),
                )
                if not ok:
                    continue
                if not cmd:
                    if getattr(settings, "wake_word_ack", True):
                        ack = str(getattr(settings, "wake_word_ack_text", "Sim?") or "Sim?").strip() or "Sim?"
                        console.print(f"Agente> {ack}")
                        if tts.enabled:
                            try:
                                tts.speak(ack)
                            except Exception:
                                logger.exception("Falha ao falar wake word ack (TTS)")
                    continue
                user_message = cmd

        memory.append("user_message", {"text": user_message})

        plan = route(settings, user_message)

        # Para mensagens de orientação/conversa, responda diretamente com LLM (sem tools).
        # Isso deixa o assistente muito mais "Jarvis" no dia-a-dia.
        if plan.intent == "chat":
            try:
                history = _build_chat_history(memory, current_user_message=user_message)
                response_text = chat_reply(settings, user_message, history=history)
                console.print(f"Agente> {response_text}")
                memory.append("agent_response", {"text": response_text})
                if tts.enabled and response_text:
                    try:
                        t = response_text.strip()
                        if len(t) > 400:
                            t = t[:400] + "..."
                        tts.speak(t)
                    except Exception:
                        logger.exception("Falha ao falar resposta (TTS)")
                continue
            except Exception as exc:  # noqa: BLE001
                # Se o chat LLM falhar (config/deps/rede), cai no caminho antigo.
                logger.exception("Falha no chat LLM")
                console.print(f"[yellow]Chat LLM indisponível:[/yellow] {exc}")

        memory.append(
            "plan",
            {
                "intent": plan.intent,
                "risk": str(plan.risk),
                "tool_calls": [c.model_dump() for c in plan.tool_calls],
            },
        )

        if plan.intent == "exit":
            console.print(plan.final_response or "Encerrando.")
            return

        # Session toggles (no tools, no HITL)
        if plan.intent in {"core.omega_on", "core.omega_off"}:
            enable = (plan.intent == "core.omega_on")
            settings = replace(
                settings,
                omega_enabled=enable,
                # Se ligar, ativa retries default; se desligar, volta ao conservador.
                retry_max_attempts=(3 if enable else 1),
            )
            console.print(f"Agente> {plan.final_response or ('Modo omega ' + ('ativado' if enable else 'desativado') + '.')}")
            memory.append(
                "session_toggle",
                {
                    "omega_enabled": settings.omega_enabled,
                    "retry_max_attempts": settings.retry_max_attempts,
                    "retry_backoff_s": settings.retry_backoff_s,
                    "retry_side_effect_tools": settings.retry_side_effect_tools,
                },
            )
            continue

        response_text = _execute_plan(console, settings, registry, plan, memory)
        if tts.enabled and response_text:
            # Evita falar textos gigantes acidentalmente.
            t = response_text.strip()
            if len(t) > 400:
                t = t[:400] + "..."
            try:
                tts.speak(t)
            except Exception:
                logger.exception("Falha ao falar resposta (TTS)")


def _build_chat_history(memory: JsonlMemoryStore, *, current_user_message: str) -> list[dict[str, str]]:
    """Monta um histórico curto para dar contexto ao chat.

    Observações:
    - Usamos apenas user_message/agent_response para não poluir com tool outputs.
    - Limitamos o tamanho para reduzir custo/latência.
    """

    events = memory.recent(limit=30)

    # Remove o último user_message (o atual), já que será adicionado separadamente.
    if events:
        e0 = events[0]
        if e0.kind == "user_message" and str((e0.payload or {}).get("text", "")).strip() == str(current_user_message).strip():
            events = events[1:]

    msgs: list[dict[str, str]] = []
    for e in reversed(events):
        if e.kind == "user_message":
            t = str((e.payload or {}).get("text", "") or "").strip()
            if t:
                msgs.append({"role": "user", "content": t})
        elif e.kind == "agent_response":
            t = str((e.payload or {}).get("text", "") or "").strip()
            if t:
                msgs.append({"role": "assistant", "content": t})

    # Mantém apenas o rastro mais recente.
    if len(msgs) > 10:
        msgs = msgs[-10:]
    return msgs


def _execute_plan(console: Console, settings: Settings, registry, plan: Plan, memory: JsonlMemoryStore) -> str | None:
    effective_risk = _effective_risk_for_plan(plan, registry, settings=settings)
    effective_plan = plan if effective_risk == plan.risk else plan.model_copy(update={"risk": effective_risk})

    normalized_plan, normalize_note = _normalize_plan_args(effective_plan, settings=settings)
    if normalize_note:
        memory.append(
            "plan_normalized_args",
            {
                "intent": effective_plan.intent,
                "note": normalize_note,
                "tool_calls": [c.model_dump() for c in normalized_plan.tool_calls],
            },
        )

    preflight_error = _preflight_validate_plan(normalized_plan, registry)
    if preflight_error:
        console.print(f"[red]Preflight error:[/red] {preflight_error}")
        memory.append(
            "preflight_error",
            {
                "intent": normalized_plan.intent,
                "risk": str(normalized_plan.risk),
                "error": preflight_error,
                "tool_calls": [c.model_dump() for c in normalized_plan.tool_calls],
            },
        )
        console.print("Agente> Não executei por segurança.")
        return None

    if effective_plan.risk != plan.risk:
        memory.append(
            "plan_effective_risk",
            {"intent": plan.intent, "router_risk": str(plan.risk), "effective_risk": str(effective_plan.risk)},
        )

    if effective_plan.risk == plan.risk:
        console.print(Panel.fit(f"Intent: {plan.intent}\nRisk: {plan.risk}", title="Plano"))
    else:
        console.print(
            Panel.fit(
                f"Intent: {plan.intent}\nRisk(router): {plan.risk}\nRisk(effective): {effective_plan.risk}",
                title="Plano",
            )
        )

    if not require_approval(
        normalized_plan,
        enabled=settings.hitl_enabled,
        min_risk=settings.hitl_min_risk,
        require_token=settings.hitl_require_token,
    ):
        console.print("Agente> Ok, não vou executar isso.")
        return None

    def _is_side_effect_tool(name: str) -> bool:
        # Heurística conservadora: ferramentas que podem causar efeitos no SO.
        # Retrys dessas ferramentas ficam desabilitados por padrão.
        return bool(
            name.startswith((
                "gui.",
                "discord.",
                "jgrasp.",
                "dev.",
                "fs.delete",
                "fs.move",
                "fs.copy",
                "write_file",
                "screen.click_text",
            ))
            or name in {"os.open_app", "os.close_app", "os.open_url"}
        )

    def _should_retry(tool_name: str, err: str) -> bool:
        # Só tenta retry quando:
        # - o usuário ativou omega/retries (>1)
        # - a tool é considerada segura (ou usuário permitiu side-effect retries)
        # - erro parece transitório (timing/foco/deps momentâneas)
        if settings.retry_max_attempts <= 1:
            return False

        side_effect = _is_side_effect_tool(tool_name)
        if side_effect and not settings.retry_side_effect_tools:
            return False

        e = (err or "").lower()
        transient_markers = [
            "timeout",
            "timed out",
            "tempor",
            "try again",
            "tente novamente",
            "not found",
            "não encontrado",
            "nao encontrado",
            "falhou",
            "failed",
            "busy",
            "ocupado",
        ]
        return any(m in e for m in transient_markers)

    def _run_with_retry(call: ToolCall):
        last = None
        for attempt in range(1, settings.retry_max_attempts + 1):
            if attempt > 1:
                sleep_s = settings.retry_backoff_s * (attempt - 1)
                if sleep_s:
                    time.sleep(sleep_s)

            result = registry.run(call.tool_name, call.args)
            memory.append(
                "tool_output",
                {
                    "tool": call.tool_name,
                    "args": call.args,
                    "attempt": attempt,
                    "status": result.status,
                    "output": result.output,
                    "error": result.error,
                },
            )

            if result.status == "ok":
                return result

            last = result
            if not _should_retry(call.tool_name, str(result.error or "")):
                break

            console.print(
                f"[yellow]Tool falhou (tentativa {attempt}/{settings.retry_max_attempts})[/yellow]: {call.tool_name}: {result.error}"
            )

        assert last is not None
        return last

    # Execução sequencial (com retry opcional).
    for call in normalized_plan.tool_calls:
        result = _run_with_retry(call)
        if result.status == "error":
            console.print(f"[red]Tool error:[/red] {call.tool_name}: {result.error}")
            console.print("Agente> Tive um erro executando o plano.")
            return None

        # Observabilidade do MVP:
        # - Em agentes, tool output é parte essencial do feedback loop.
        # - Truncamos para não poluir o terminal nem expor dados demais por acidente.
        if result.status == "ok" and result.output:
            out = result.output.strip()
            if len(out) > 2000:
                out = out[:2000] + "\n... [truncado]"
            console.print(Panel(out, title=f"Tool: {call.tool_name}"))

    if normalized_plan.final_response:
        console.print(f"Agente> {normalized_plan.final_response}")
        memory.append("agent_response", {"text": normalized_plan.final_response})
        return normalized_plan.final_response
    else:
        console.print("Agente> Feito.")
        memory.append("agent_response", {"text": "Feito."})
        return "Feito."


def _normalize_plan_args(plan: Plan, *, settings: Settings) -> tuple[Plan, str | None]:
    """Normaliza args de tool calls (sem relaxar regras de segurança).

    Ex.: remover aspas, trocar \\ por / em paths, converter números.
    """

    changed = False
    notes: list[str] = []
    new_calls: list[ToolCall] = []

    for call in plan.tool_calls:
        norm_args, note, did_change = _normalize_tool_args(call.tool_name, call.args, settings=settings)
        if did_change:
            changed = True
        if note:
            notes.append(f"{call.tool_name}: {note}")
        new_calls.append(call.model_copy(update={"args": norm_args}))

    if not changed:
        return plan, None

    return plan.model_copy(update={"tool_calls": new_calls}), "; ".join(notes)[:300]


def _normalize_tool_args(tool_name: str, args: dict, *, settings: Settings) -> tuple[dict, str | None, bool]:
    a = dict(args or {})
    did = False
    note_parts: list[str] = []

    def to_intish(v) -> int:
        """Best-effort conversion for coordinates.

        Accepts: int, float, numeric strings like "123", "123.0", "123,0".
        """

        if v is None:
            raise ValueError("none")
        if isinstance(v, bool):
            raise ValueError("bool")
        if isinstance(v, int):
            return int(v)
        if isinstance(v, float):
            return int(round(v))
        s = str(v).strip()
        if not s:
            raise ValueError("empty")
        # Handle comma decimal separator (pt-BR) when no dot exists.
        if "," in s and "." not in s:
            s = s.replace(",", ".")
        f = float(s)
        return int(round(f))

    def norm_str(v) -> str:
        return str(v).strip()

    def norm_path(v) -> str:
        s = norm_str(v)
        s = s.strip('"').strip("'")
        s = s.replace("\\", "/")
        return s

    # Paths comuns
    if tool_name in {"write_file", "fs.list_dir", "fs.read_text", "fs.delete", "fs.mkdir", "os.mkdir"} and "path" in a:
        before = a.get("path")
        after = norm_path(before)
        if before != after:
            a["path"] = after
            did = True
            note_parts.append("path normalized")

    if tool_name == "os.mkdir":
        for key in ("known_folder", "name"):
            if key in a and a.get(key) is not None:
                before = a.get(key)
                after = norm_str(before).strip('"').strip("'")
                if before != after:
                    a[key] = after
                    did = True
                    note_parts.append(f"{key} trimmed")

    if tool_name in {"fs.copy", "fs.move"}:
        for key in ("src", "dst"):
            if key in a:
                before = a.get(key)
                after = norm_path(before)
                if before != after:
                    a[key] = after
                    did = True
                    note_parts.append(f"{key} normalized")

    if tool_name == "screen.ocr" and "image_path" in a and a.get("image_path") is not None:
        before = a.get("image_path")
        after = norm_path(before)
        if before != after:
            a["image_path"] = after
            did = True
            note_parts.append("image_path normalized")

    # Web URLs
    if tool_name in {"web.get_page_text", "web.screenshot"} and "url" in a:
        before = a.get("url")
        after = norm_str(before)
        if settings.web_assume_https and after and not after.lower().startswith(("http://", "https://")):
            after = "https://" + after
            note_parts.append("assumed https")
        if before != after:
            a["url"] = after
            did = True
            note_parts.append("url trimmed")

    if tool_name == "web.screenshot" and "path" in a and a.get("path") is not None:
        before = a.get("path")
        after = norm_path(before)
        if before != after:
            a["path"] = after
            did = True
            note_parts.append("output path normalized")

    # Números
    if tool_name == "memory.search":
        if "limit" in a:
            try:
                a["limit"] = int(str(a.get("limit")))
                did = True
                note_parts.append("limit int")
            except Exception:
                pass

    if tool_name in {"web.get_page_text", "fs.read_text"}:
        if "max_chars" in a:
            try:
                a["max_chars"] = int(str(a.get("max_chars")))
                did = True
                note_parts.append("max_chars int")
            except Exception:
                pass

    if tool_name in {"gui.move_mouse", "gui.click"}:
        for k in ("x", "y"):
            if k in a:
                try:
                    a[k] = to_intish(a.get(k))
                    did = True
                except Exception:
                    pass

    if tool_name == "gui.type_text" and "text" in a:
        before = a.get("text")
        after = norm_str(before)
        if before != after:
            a["text"] = after
            did = True
            note_parts.append("text trimmed")

    if tool_name == "dev.exec" and "command" in a:
        before = a.get("command")
        after = norm_str(before)
        if before != after:
            a["command"] = after
            did = True
            note_parts.append("command trimmed")

    if tool_name in {"dev.exec", "dev.run_python", "dev.autofix_python_file", "dev.autofix_cmd"}:
        if "timeout_s" in a:
            try:
                a["timeout_s"] = float(str(a.get("timeout_s")))
                did = True
                note_parts.append("timeout_s float")
            except Exception:
                pass

    if tool_name in {"dev.autofix_python_file"} and "path" in a:
        before = a.get("path")
        after = norm_path(before)
        if before != after:
            a["path"] = after
            did = True
            note_parts.append("path normalized")

    if tool_name == "dev.autofix_cmd" and "command" in a:
        before = a.get("command")
        after = norm_str(before)
        if before != after:
            a["command"] = after
            did = True
            note_parts.append("command trimmed")

    if tool_name == "os.close_app":
        if "app" in a:
            before = a.get("app")
            after = norm_str(before).lower().replace(" ", "").replace("_", "")
            if before != after:
                a["app"] = after
                did = True
                note_parts.append("app normalized")
        if "title_contains" in a and a.get("title_contains") is not None:
            before = a.get("title_contains")
            after = norm_str(before)
            if before != after:
                a["title_contains"] = after
                did = True
                note_parts.append("title_contains trimmed")
        if "timeout_s" in a:
            try:
                a["timeout_s"] = float(str(a.get("timeout_s")))
                did = True
                note_parts.append("timeout_s float")
            except Exception:
                pass

    note = ", ".join(note_parts) if note_parts else None
    return a, note, did


def _effective_risk_for_plan(plan: Plan, registry, *, settings: Settings | None = None) -> RiskLevel:
    """Calcula o risco efetivo (router + risco intrínseco das tools).

    Motivação:
    - O router/LLM pode subestimar risco.
    - Tools têm um risco intrínseco declarado no registry.

    Política:
    - Risco efetivo = max(router_risk, max(tool_risk)).
    - Tool desconhecida => CRITICAL (fail closed).
    """

    def rank(r: RiskLevel) -> int:
        return {
            RiskLevel.LOW: 0,
            RiskLevel.MEDIUM: 1,
            RiskLevel.HIGH: 2,
            RiskLevel.CRITICAL: 3,
        }.get(r, 3)

    def parse_tool_risk(risk_str: str) -> RiskLevel:
        raw = (risk_str or "LOW").strip().upper()
        try:
            return RiskLevel(raw)
        except Exception:
            return RiskLevel.LOW

    def _load_open_apps_from_settings(settings: Settings | None) -> dict[str, str]:
        if settings is None:
            return {}

        out: dict[str, str] = {}

        def _merge(mapping) -> None:
            if not isinstance(mapping, dict):
                return
            for k, v in mapping.items():
                key = str(k).strip().lower()
                if not key:
                    continue
                out[key] = str(v).strip()

        raw_json = (settings.open_apps_json or "").strip()
        if raw_json:
            try:
                _merge(json.loads(raw_json))
            except Exception:
                pass

        raw_file = (settings.open_apps_file or "").strip()
        if raw_file:
            try:
                p = Path(raw_file)
                if not p.is_absolute():
                    p = Path.cwd() / p
                if p.exists() and p.is_file():
                    _merge(json.loads(p.read_text(encoding="utf-8", errors="replace")))
            except Exception:
                pass

        return out

    def dynamic_tool_risk(tool_name: str, args: dict) -> RiskLevel | None:
        """Eleva risco com base em args (política de segurança).

        Nota:
        - Isso existe para casos onde a mesma tool pode ser segura ou perigosa
          dependendo do alvo (ex: abrir apps comuns vs. abrir cmd/powershell).
        """

        if tool_name == "os.open_app":
            app = str((args or {}).get("app", "")).strip().lower()
            # Normaliza: remove espaços e underscores para comparar com mais robustez.
            app_norm = app.replace(" ", "").replace("_", "")
            dangerous_keys = {
                # shells / scripting
                "cmd",
                "commandprompt",
                "powershell",
                "pwsh",
                "terminal",
                "windows terminal",
                "wscript",
                "cscript",
                "mshta",
                "rundll32",
                # registry / scheduled tasks
                "regedit",
                "registry",
                "reg",
                "taskschd",
                "schtasks",
            }
            dangerous_norm = {k.replace(" ", "").replace("_", "") for k in dangerous_keys}
            if app_norm in dangerous_norm:
                return RiskLevel.CRITICAL

            # Se o app for um alias customizado, resolvemos o target via Settings.
            # Assim também pedimos HITL quando o target é um executável perigoso.
            extra = _load_open_apps_from_settings(settings)
            target = str(extra.get(app, "")).strip()
            if target:
                base = os.path.basename(target).lower()
                dangerous_basenames = {
                    "cmd.exe",
                    "powershell.exe",
                    "pwsh.exe",
                    "wscript.exe",
                    "cscript.exe",
                    "mshta.exe",
                    "rundll32.exe",
                    "reg.exe",
                    "regedit.exe",
                    "schtasks.exe",
                }
                if base in dangerous_basenames:
                    return RiskLevel.CRITICAL

        return None

    current = plan.risk

    for call in plan.tool_calls:
        try:
            spec = registry.get(call.tool_name)
            tool_risk = parse_tool_risk(getattr(spec, "risk", "LOW"))
        except Exception:
            tool_risk = RiskLevel.CRITICAL

        dyn = dynamic_tool_risk(call.tool_name, call.args)
        if dyn is not None and rank(dyn) > rank(tool_risk):
            tool_risk = dyn

        if rank(tool_risk) > rank(current):
            current = tool_risk

    return current


def _preflight_validate_plan(plan: Plan, registry) -> str | None:
    """Valida tool calls antes de executar.

    Objetivo:
    - Defesa em profundidade: não depende só do router nem só das tools.
    - Falha cedo antes de pedir HITL/executar.

    Política (MVP):
    - Paths devem ser relativos, sem '..' e sem drive.
    - URLs devem ser http(s) quando exigidas.
    - Campos obrigatórios devem existir.
    """

    for call in plan.tool_calls:
        err = _preflight_validate_tool_call(call.tool_name, call.args, registry)
        if err:
            return f"{call.tool_name}: {err}"
    return None


def _is_safe_rel_path(path: str) -> bool:
    p = (path or "").strip().replace("\\", "/")
    if not p:
        return False
    if p.startswith("/") or ":" in p:
        return False
    if ".." in p.split("/"):
        return False
    return True


def _is_http_url(url: str) -> bool:
    u = (url or "").strip().lower()
    return u.startswith("http://") or u.startswith("https://")


def _looks_like_domain(url: str) -> bool:
    u = (url or "").strip()
    if not u or " " in u:
        return False
    if u.startswith("/") or ":" in u:
        return False
    return bool(re.search(r"^[a-zA-Z0-9][\w.-]+\.[a-zA-Z]{2,}(/.*)?$", u))


def _preflight_validate_tool_call(tool_name: str, args: dict, registry) -> str | None:
    # Tool desconhecida => bloqueia.
    try:
        registry.get(tool_name)
    except Exception:
        return "tool não registrada (talvez dependência opcional não instalada). Rode: omniscia doctor"

    a = args or {}

    # Paths
    if tool_name in {"write_file", "fs.list_dir", "fs.read_text", "fs.delete"}:
        path = str(a.get("path", "")).strip()
        if not _is_safe_rel_path(path) and path != ".":
            return "path inválido (use path relativo, sem '..' e sem drive)"

    if tool_name == "screen.ocr":
        image_path = a.get("image_path")
        if image_path is not None:
            p = str(image_path).strip()
            if p and not _is_safe_rel_path(p):
                return "image_path inválido (use path relativo)"

    if tool_name == "web.screenshot":
        url = str(a.get("url", "")).strip()
        if not _is_http_url(url):
            if _looks_like_domain(url):
                return f"url inválida (use http/https). Tente: https://{url}"
            return "url inválida (use http/https)"
        out_path = a.get("path")
        if out_path is not None and str(out_path).strip():
            if not _is_safe_rel_path(str(out_path)):
                return "path inválido (use path relativo)"

    if tool_name == "web.get_page_text":
        url = str(a.get("url", "")).strip()
        if not _is_http_url(url):
            if _looks_like_domain(url):
                return f"url inválida (use http/https). Tente: https://{url}"
            return "url inválida (use http/https)"

    if tool_name == "dev.autofix_python_file":
        path = str(a.get("path", "")).strip()
        if not _is_safe_rel_path(path) or not path.lower().endswith(".py"):
            return "path inválido (use path relativo .py)"

    if tool_name == "dev.autofix_cmd":
        command = str(a.get("command", "")).strip()
        if not command:
            return "command vazio"

    if tool_name == "dev.exec":
        command = str(a.get("command", "")).strip()
        if not command:
            return "command vazio"
        if len(command) > 5000:
            return "command muito longo"

        # Validação extra: executável allowlisted (defesa em profundidade).
        try:
            from omniscia.modules.dev_agent.sandbox import is_allowlisted, parse_command

            argv = parse_command(command)
            if not argv:
                return "command vazio"
            if not is_allowlisted(argv):
                return f"executável não allowlisted: {argv[0]}"
        except Exception:
            # Se falhar ao importar/parsing, não liberamos nada extra aqui.
            pass

        if "timeout_s" in a:
            try:
                t = float(str(a.get("timeout_s")))
            except Exception:
                return "timeout_s inválido"
            if t <= 0 or t > 300:
                return "timeout_s fora do limite (0 < timeout_s <= 300)"

    if tool_name == "dev.run_python":
        # Pelo menos um entre code/module/script.
        if not any(k in a and str(a.get(k, "")).strip() for k in ("code", "module", "script")):
            return "informe code, module ou script"
        if a.get("script"):
            script = str(a.get("script", "")).strip()
            if not _is_safe_rel_path(script):
                return "script inválido (use path relativo)"

        if "timeout_s" in a:
            try:
                t = float(str(a.get("timeout_s")))
            except Exception:
                return "timeout_s inválido"
            if t <= 0 or t > 300:
                return "timeout_s fora do limite (0 < timeout_s <= 300)"

    if tool_name == "os.close_app":
        app = str(a.get("app", "") or "").strip()
        title_contains = str(a.get("title_contains", "") or "").strip()
        if not app and not title_contains:
            return "informe app ou title_contains"
        if "timeout_s" in a:
            try:
                t = float(str(a.get("timeout_s")))
            except Exception:
                return "timeout_s inválido"
            if t <= 0 or t > 20:
                return "timeout_s fora do limite (0 < timeout_s <= 20)"

    # GUI args básicos
    if tool_name in {"gui.move_mouse", "gui.click"}:
        for k in ("x", "y"):
            if k not in a:
                return f"faltando {k}"
            try:
                val = a.get(k, "")
                # Aceita int-ish (ex: 123.0) e strings numéricas.
                if isinstance(val, bool):
                    raise ValueError("bool")
                if isinstance(val, int):
                    n = int(val)
                elif isinstance(val, float):
                    n = int(round(val))
                else:
                    s = str(val).strip()
                    if "," in s and "." not in s:
                        s = s.replace(",", ".")
                    n = int(round(float(s)))
            except Exception:
                return f"{k} deve ser int"

            if n < 0 or n > 20000:
                return f"{k} fora do limite (0..20000)"

    if tool_name == "gui.type_text":
        if "text" not in a:
            return "faltando text"
        text = a.get("text")
        if not isinstance(text, str):
            return "text deve ser string"
        if not text.strip():
            return "text vazio"
        if len(text) > 2000:
            return "text muito longo (max 2000 chars)"
        if "\x00" in text:
            return "text contém caractere inválido"

    # Qualquer outra tool: sem validação extra aqui.
    return None
