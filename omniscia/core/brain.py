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
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

from omniscia.core.config import Settings
from omniscia.core.hitl import require_approval
from omniscia.core.router import route
from omniscia.core.tools import build_default_registry
from omniscia.core.types import Plan, RiskLevel, ToolCall
from omniscia.modules.stt.factory import build_stt
from omniscia.modules.memory.store import JsonlMemoryStore

logger = logging.getLogger(__name__)


def run_brain_loop(settings: Settings) -> None:
    """Loop REPL do agente."""

    console = Console()
    memory = JsonlMemoryStore()
    registry = build_default_registry(settings=settings, memory_store=memory)
    stt = build_stt(settings, console=console)

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
            settings = Settings(
                **{**settings.__dict__, "stt_mode": "text"},  # type: ignore[arg-type]
            )
            stt = build_stt(settings, console=console)
            continue

        if not user_message:
            continue

        memory.append("user_message", {"text": user_message})

        plan = route(settings, user_message)

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

        _execute_plan(console, settings, registry, plan, memory)


def _execute_plan(console: Console, settings: Settings, registry, plan: Plan, memory: JsonlMemoryStore) -> None:
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
        return

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
        return

    # Execução sequencial simples.
    for call in normalized_plan.tool_calls:
        result = registry.run(call.tool_name, call.args)
        if result.status == "error":
            console.print(f"[red]Tool error:[/red] {call.tool_name}: {result.error}")
            console.print("Agente> Tive um erro executando o plano.")
            return

        memory.append(
            "tool_output",
            {
                "tool": call.tool_name,
                "args": call.args,
                "status": result.status,
                "output": result.output,
                "error": result.error,
            },
        )

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
    else:
        console.print("Agente> Feito.")
        memory.append("agent_response", {"text": "Feito."})


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
        return "tool não registrada"

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
