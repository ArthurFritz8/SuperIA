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
import threading
import time
from pathlib import Path
from dataclasses import replace
from rich.console import Console
from rich.panel import Panel

from omniscia.core.config import Settings
from omniscia.core.hitl import require_approval
from omniscia.core.router import route, route_llm
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

    # Lock para evitar concorrência no TTS (alguns engines não são thread-safe).
    tts_lock = threading.Lock()

    # Memória vetorial (opt-in) para RAG. Best-effort: se deps faltarem, seguimos sem.
    vector_memory = None
    if getattr(settings, "vector_memory_enabled", False):
        try:
            from omniscia.modules.memory.vector_store import ChromaVectorMemory

            vector_memory = ChromaVectorMemory(
                persist_dir="data/chroma",
                collection="omniscia_memory",
                embed_model="all-MiniLM-L6-v2",
            )
            console.print("[dim]Memória vetorial habilitada (RAG).[/dim]")
        except Exception as exc:  # noqa: BLE001
            console.print(f"[yellow]Memória vetorial indisponível:[/yellow] {exc}")

    # Hotkey (opt-in): Ctrl+Space arma captura de tela (screenshot + OCR) para a próxima mensagem.
    screen_hotkey_flag = threading.Event()
    if getattr(settings, "hotkey_screen_enabled", False):
        try:
            from omniscia.core.hotkeys import start_screen_hotkey_listener

            start_screen_hotkey_listener(screen_hotkey_flag)
            console.print("[dim]Hotkey habilitada: Ctrl+Space (capturar contexto de tela).[/dim]")
        except Exception as exc:  # noqa: BLE001
            console.print(f"[yellow]Hotkey indisponível:[/yellow] {exc}")

    # Proatividade (opt-in): alerta quando CPU/RAM estiverem muito altas.
    if getattr(settings, "proactive_enabled", False):
        try:
            from omniscia.core.proactive import start_proactive_scheduler

            def _on_alert(msg: str) -> None:
                # Apenas alerta + pergunta; sem ações automáticas.
                memory.append("proactive_alert", {"text": msg})
                console.print(f"\n[bold yellow]VOID>[/bold yellow] {msg}")
                if tts.enabled and getattr(settings, "tts_speak_alerts", False):
                    try:
                        with tts_lock:
                            tts.speak(msg[:220] + ("..." if len(msg) > 220 else ""))
                    except Exception:
                        logger.exception("Falha ao falar alerta proativo (TTS)")

            start_proactive_scheduler(
                interval_s=int(getattr(settings, "proactive_interval_s", 300)),
                cpu_threshold=int(getattr(settings, "proactive_cpu_threshold", 95)),
                ram_threshold=int(getattr(settings, "proactive_ram_threshold", 95)),
                on_alert=_on_alert,
            )
            console.print("[dim]Proatividade habilitada (scheduler em background).[/dim]")
        except Exception as exc:  # noqa: BLE001
            console.print(f"[yellow]Proatividade indisponível:[/yellow] {exc}")

    console.print(Panel.fit("Omnisciência (MVP) — digite seu comando (ou 'sair')", title="OK"))

    while True:
        hotkey_image_path: str | None = None
        hotkey_ocr_text: str | None = None
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

        # Se a hotkey foi pressionada, capturamos contexto de tela antes de rotear.
        if screen_hotkey_flag.is_set():
            screen_hotkey_flag.clear()
            try:
                # Consideramos hotkey como pedido explícito de visão.
                console.print("[dim]Capturando contexto de tela (hotkey)...[/dim]")
                # screenshot
                res1 = registry.run("screen.screenshot", {})
                if res1.status == "ok":
                    hotkey_image_path = "data/screenshots/latest.png"
                memory.append(
                    "tool_output",
                    {
                        "tool": "screen.screenshot",
                        "args": {},
                        "attempt": 1,
                        "status": res1.status,
                        "output": res1.output,
                        "error": res1.error,
                    },
                )
                # OCR (usa latest.png por padrão no tool)
                res2 = registry.run("screen.ocr", {})
                if res2.status == "ok":
                    hotkey_ocr_text = (res2.output or "").strip() or None
                memory.append(
                    "tool_output",
                    {
                        "tool": "screen.ocr",
                        "args": {},
                        "attempt": 1,
                        "status": res2.status,
                        "output": res2.output,
                        "error": res2.error,
                    },
                )
                if res2.status == "ok" and (res2.output or "").strip():
                    console.print(Panel(str(res2.output)[:2000], title="OCR (hotkey)"))

                # Evento compacto para o LLM entender que o usuário chamou via hotkey.
                memory.append(
                    "screen_context",
                    {
                        "image_path": hotkey_image_path,
                        "ocr": hotkey_ocr_text,
                        "note": "Usuário acionou hotkey (Ctrl+Space) para ajuda contextual da tela.",
                    },
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Falha capturando contexto de tela")
                console.print(f"[yellow]Falha ao capturar tela:[/yellow] {exc}")

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
                        if tts.enabled and getattr(settings, "tts_speak_wake_ack", False):
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
                history = _build_chat_history(
                    memory,
                    current_user_message=user_message,
                    vector_memory=vector_memory,
                )

                # Se houver OCR recente, adiciona ao texto para o LLM ter contexto explícito.
                effective_user_message = user_message
                if hotkey_ocr_text:
                    ocr_snip = hotkey_ocr_text
                    if len(ocr_snip) > 2000:
                        ocr_snip = ocr_snip[:2000] + "\n... [truncado]"
                    effective_user_message = (
                        effective_user_message
                        + "\n\n[Contexto de tela: OCR]"
                        + "\n"
                        + ocr_snip
                    )

                # VLM (opt-in): se o hotkey capturou screenshot nesta rodada, podemos anexar a imagem.
                # Isso pode enviar conteúdo da tela para um provider externo; exigimos HITL em nível CRITICAL.
                image_path = hotkey_image_path if getattr(settings, "vlm_enabled", False) else None
                if image_path:
                    approval_plan = Plan(
                        intent="vlm.chat_with_image",
                        user_message=user_message,
                        tool_calls=[
                            ToolCall(
                                tool_name="vlm.chat",
                                args={
                                    "image_path": image_path,
                                    "note": "Enviar screenshot anexado para o LLM (multimodal) para analisar a tela.",
                                },
                            )
                        ],
                        risk=RiskLevel.CRITICAL,
                        final_response="Vou anexar a captura de tela ao LLM para analisar.",
                    )
                    if not require_approval(
                        approval_plan,
                        enabled=settings.hitl_enabled,
                        min_risk=settings.hitl_min_risk,
                        require_token=settings.hitl_require_token,
                    ):
                        image_path = None

                response_text = chat_reply(
                    settings,
                    effective_user_message,
                    history=history,
                    image_path=image_path,
                )
                console.print(f"Agente> {response_text}")
                memory.append("agent_response", {"text": response_text})

                # Aprendizagem contínua (opt-in): sintetiza uma memória e salva no Chroma.
                if (
                    getattr(settings, "vector_memory_enabled", False)
                    and getattr(settings, "vector_memory_auto_remember", False)
                    and settings.router_mode == "llm"
                ):
                    _auto_remember_best_effort(
                        console=console,
                        settings=settings,
                        registry=registry,
                        memory=memory,
                        user_message=user_message,
                        assistant_response=response_text,
                    )

                if tts.enabled and getattr(settings, "tts_speak_responses", False) and response_text:
                    try:
                        t = response_text.strip()
                        if len(t) > 400:
                            t = t[:400] + "..."
                        with tts_lock:
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

        # Voice toggles (TTS) — não usa tools, não passa por HITL.
        if plan.intent in {"core.voice_on", "core.voice_off"}:
            enable = (plan.intent == "core.voice_on")

            if enable:
                # Liga engine + fala respostas (apenas). Alertas e wake ack continuam desligados.
                settings = replace(
                    settings,
                    tts_mode="pyttsx3",
                    tts_speak_responses=True,
                    tts_speak_alerts=False,
                    tts_speak_wake_ack=False,
                )
            else:
                # Silencia total + desliga engine.
                settings = replace(
                    settings,
                    tts_mode="none",
                    tts_speak_responses=False,
                    tts_speak_alerts=False,
                    tts_speak_wake_ack=False,
                )

            # Recria provider com as novas settings.
            tts = build_tts(settings, console=console)

            msg = plan.final_response or ("Voz ativada." if enable else "Voz desativada.")
            if enable and not getattr(tts, "enabled", False):
                msg = msg + " (TTS não disponível neste ambiente.)"
            console.print(f"Agente> {msg}")
            memory.append(
                "voice_toggle",
                {
                    "tts_mode": settings.tts_mode,
                    "tts_speak_responses": getattr(settings, "tts_speak_responses", False),
                    "tts_speak_alerts": getattr(settings, "tts_speak_alerts", False),
                    "tts_speak_wake_ack": getattr(settings, "tts_speak_wake_ack", False),
                    "tts_enabled": getattr(tts, "enabled", False),
                },
            )
            continue

        # ReAct (modo llm): executa tools em um loop e replaneja com base nos outputs.
        # No modo heurístico, mantemos execução linear de um plano fixo.
        if settings.router_mode == "llm" and plan.tool_calls:
            response_text = _execute_plan_react(console, settings, registry, plan, memory)
        else:
            response_text = _execute_plan(console, settings, registry, plan, memory)
        if tts.enabled and getattr(settings, "tts_speak_responses", False) and response_text:
            # Evita falar textos gigantes acidentalmente.
            t = response_text.strip()
            if len(t) > 400:
                t = t[:400] + "..."
            try:
                tts.speak(t)
            except Exception:
                logger.exception("Falha ao falar resposta (TTS)")


def _build_chat_history(
    memory: JsonlMemoryStore,
    *,
    current_user_message: str,
    vector_memory=None,
) -> list[dict[str, str]]:
    """Monta um histórico curto para dar contexto ao chat.

    Observações:
    - Incluímos um resumo truncado de tool outputs para dar contexto real ao LLM.
    - Limitamos o tamanho para reduzir custo/latência.
    """

    events = memory.recent(limit=30)

    # Remove o último user_message (o atual), já que será adicionado separadamente.
    if events:
        e0 = events[0]
        if e0.kind == "user_message" and str((e0.payload or {}).get("text", "")).strip() == str(current_user_message).strip():
            events = events[1:]

    msgs: list[dict[str, str]] = []

    # RAG (memória vetorial): injeta hits mais relevantes como contexto do assistente.
    if vector_memory is not None:
        try:
            hits = vector_memory.query(query=str(current_user_message or ""), limit=4)
            if hits:
                lines: list[str] = ["MEMÓRIA RECUPERADA (vetorial):"]
                for h in hits:
                    t = (h.text or "").strip()
                    if len(t) > 500:
                        t = t[:500] + "..."
                    lines.append(f"- [{h.score:.2f}] {t}")
                blob = "\n".join(lines)
                if len(blob) > 1800:
                    blob = blob[:1800] + "\n... [truncado]"
                msgs.append({"role": "assistant", "content": blob})
        except Exception:
            logger.exception("Falha consultando memória vetorial (best-effort)")
    for e in reversed(events):
        if e.kind == "user_message":
            t = str((e.payload or {}).get("text", "") or "").strip()
            if t:
                msgs.append({"role": "user", "content": t})
        elif e.kind == "agent_response":
            t = str((e.payload or {}).get("text", "") or "").strip()
            if t:
                msgs.append({"role": "assistant", "content": t})
        elif e.kind == "tool_output":
            tool = str((e.payload or {}).get("tool", "") or "").strip()
            status = str((e.payload or {}).get("status", "") or "").strip()
            output = str((e.payload or {}).get("output", "") or "").strip()
            error = str((e.payload or {}).get("error", "") or "").strip()

            text = f"TOOL_RESULT {tool} status={status}"
            if output:
                out = output
                if len(out) > 800:
                    out = out[:800] + "\n... [truncado]"
                text += "\nOUTPUT:\n" + out
            if error:
                err = error
                if len(err) > 500:
                    err = err[:500] + "... [truncado]"
                text += "\nERROR:\n" + err

            if tool:
                msgs.append({"role": "assistant", "content": text})

        elif e.kind == "proactive_alert":
            t = str((e.payload or {}).get("text", "") or "").strip()
            if t:
                msgs.append({"role": "assistant", "content": "PROACTIVE_ALERT: " + t})

        elif e.kind == "screen_context":
            note = str((e.payload or {}).get("note", "") or "").strip()
            ocr = str((e.payload or {}).get("ocr", "") or "").strip()
            parts: list[str] = []
            if note:
                parts.append(note)
            if ocr:
                if len(ocr) > 1200:
                    ocr = ocr[:1200] + "\n... [truncado]"
                parts.append("OCR:\n" + ocr)
            if parts:
                msgs.append({"role": "assistant", "content": "SCREEN_CONTEXT:\n" + "\n".join(parts)})

    # Mantém apenas o rastro mais recente.
    if len(msgs) > 10:
        msgs = msgs[-10:]
    return msgs


def _auto_remember_best_effort(
    *,
    console: Console,
    settings: Settings,
    registry,
    memory: JsonlMemoryStore,
    user_message: str,
    assistant_response: str,
) -> None:
    """Gera e salva uma memória curta via tool memory.remember (opt-in).

    Estratégia:
    - Best-effort (não pode quebrar a conversa).
    - Usa o router LLM para sintetizar um texto de memória.
    - Executa SOMENTE memory.remember; qualquer outra tool é ignorada.
    """

    try:
        # Só vale a pena para respostas mais "densas".
        if len((assistant_response or "").strip()) < 450:
            return

        prompt = (
            "INTERNAL: Gere uma memória curta e durável para eu lembrar no futuro. "
            "Se não houver nada útil para lembrar, retorne tool_calls=[] e final_response=''. "
            "Se houver, use APENAS a tool memory.remember com args {text, topic?, tags?}. "
            "O campo text deve ter 1-4 linhas, objetivo e reutilizável."
        )

        ctx = [
            {"role": "user", "content": str(user_message or "").strip()},
            {"role": "assistant", "content": str(assistant_response or "").strip()[:2000]},
        ]

        plan = route_llm(settings, prompt, context_messages=ctx)
        if plan is None or not plan.tool_calls:
            return

        # Permite apenas memory.remember
        calls = [c for c in plan.tool_calls if (c.tool_name or "").strip() == "memory.remember"]
        if not calls:
            return

        call = calls[0]
        res = registry.run("memory.remember", dict(call.args or {}))
        memory.append(
            "tool_output",
            {
                "tool": "memory.remember",
                "args": dict(call.args or {}),
                "attempt": 1,
                "status": res.status,
                "output": res.output,
                "error": res.error,
            },
        )
    except Exception as exc:  # noqa: BLE001
        console.print(f"[dim]Auto-remember falhou (best-effort):[/dim] {exc}")


def _is_side_effect_tool(name: str) -> bool:
    # Heurística conservadora: ferramentas que podem causar efeitos no SO.
    # Retrys dessas ferramentas ficam desabilitados por padrão.
    return bool(
        name.startswith(
            (
                "gui.",
                "discord.",
                "jgrasp.",
                "dev.",
                "fs.delete",
                "fs.move",
                "fs.copy",
                "write_file",
                "screen.click_text",
            )
        )
        or name in {"os.open_app", "os.close_app", "os.open_url"}
    )


def _should_retry(settings: Settings, tool_name: str, err: str) -> bool:
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


def _run_tool_with_retry(console: Console, settings: Settings, registry, call: ToolCall, memory: JsonlMemoryStore):
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
        if not _should_retry(settings, call.tool_name, str(result.error or "")):
            break

        console.print(
            f"[yellow]Tool falhou (tentativa {attempt}/{settings.retry_max_attempts})[/yellow]: {call.tool_name}: {result.error}"
        )

    assert last is not None
    return last


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

    preflight_error = _preflight_validate_plan(normalized_plan, registry, settings=settings)
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

    # Execução sequencial (com retry opcional).
    for call in normalized_plan.tool_calls:
        result = _run_tool_with_retry(console, settings, registry, call, memory)
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


def _execute_plan_react(console: Console, settings: Settings, registry, plan: Plan, memory: JsonlMemoryStore) -> str | None:
    """Executa tools em loop, replanejando com base em tool outputs (ReAct-ish).

    Política:
    - Executa no máximo alguns passos para evitar loops.
    - Pede HITL em cada tool call (porque o plano pode mudar a cada passo).
    """

    max_steps = 6
    original_user_message = (plan.user_message or "").strip()
    current_plan = plan

    # Algumas tools são "single-shot" (fazem o trabalho inteiro em uma chamada).
    # Se elas forem executadas com sucesso num plano determinístico (intent == tool_name),
    # não replanejamos via LLM para evitar respostas genéricas e rate limits.
    single_shot_tools = {
        "edu.pdf_word_autofill",
    }

    # Mantém um rastro curto para dar ao LLM.
    trace_messages: list[dict[str, str]] = []

    for step in range(1, max_steps + 1):
        # Se o plano atual já não tem tools, finalizamos.
        if not current_plan.tool_calls:
            text = (current_plan.final_response or "").strip() or "Feito."
            console.print(f"Agente> {text}")
            memory.append("agent_response", {"text": text})
            return text

        # Executa apenas 1 tool por passo.
        call = current_plan.tool_calls[0]
        step_plan = current_plan.model_copy(update={"tool_calls": [call]})

        # Preflight + HITL por passo.
        effective_risk = _effective_risk_for_plan(step_plan, registry, settings=settings)
        effective_plan = step_plan if effective_risk == step_plan.risk else step_plan.model_copy(update={"risk": effective_risk})
        normalized_plan, _ = _normalize_plan_args(effective_plan, settings=settings)

        preflight_error = _preflight_validate_plan(normalized_plan, registry, settings=settings)
        if preflight_error:
            console.print(f"[red]Preflight error:[/red] {preflight_error}")
            console.print("Agente> Não executei por segurança.")
            return None

        console.print(Panel.fit(f"ReAct step {step}/{max_steps}\nTool: {call.tool_name}\nRisk: {normalized_plan.risk}", title="Plano"))

        if not require_approval(
            normalized_plan,
            enabled=settings.hitl_enabled,
            min_risk=settings.hitl_min_risk,
            require_token=settings.hitl_require_token,
        ):
            console.print("Agente> Ok, não vou executar isso.")
            return None

        result = _run_tool_with_retry(console, settings, registry, call, memory)
        if result.status == "error":
            console.print(f"[red]Tool error:[/red] {call.tool_name}: {result.error}")

        if result.output:
            out = result.output.strip()
            if len(out) > 2000:
                out = out[:2000] + "\n... [truncado]"
            console.print(Panel(out, title=f"Tool: {call.tool_name}"))

        # Short-circuit: deterministic single-shot tool finished successfully.
        if (
            result.status == "ok"
            and call.tool_name in single_shot_tools
            and (current_plan.intent or "").strip() == call.tool_name
        ):
            text = (result.output or "").strip() or "Feito."
            console.print(f"Agente> {text}")
            memory.append("agent_response", {"text": text})
            return text

        # Alimenta o LLM com um resumo do que aconteceu.
        out_short = (result.output or "").strip()
        if len(out_short) > 1200:
            out_short = out_short[:1200] + "\n... [truncado]"
        err_short = str(result.error or "").strip()
        if len(err_short) > 800:
            err_short = err_short[:800] + "... [truncado]"

        trace = {
            "tool": call.tool_name,
            "args": call.args,
            "status": result.status,
            "output": out_short,
            "error": err_short,
        }
        trace_messages.append({"role": "assistant", "content": "TOOL_RESULT " + json.dumps(trace, ensure_ascii=False)})
        if len(trace_messages) > 8:
            trace_messages = trace_messages[-8:]

        # Se o plano original tinha mais tools, guardamos um hint para o LLM.
        if len(current_plan.tool_calls) > 1:
            trace_messages.append(
                {
                    "role": "assistant",
                    "content": "HINT: o plano anterior continha mais tool_calls; replaine considerando o objetivo original.",
                }
            )
            if len(trace_messages) > 8:
                trace_messages = trace_messages[-8:]

        # Replaneja via LLM (mantendo o pedido original e fornecendo o rastro).
        new_plan = route_llm(settings, original_user_message, context_messages=trace_messages)
        if new_plan is None:
            console.print("[yellow]Não consegui replanejar via LLM; parei por segurança.[/yellow]")
            return None

        memory.append(
            "plan",
            {
                "intent": new_plan.intent,
                "risk": str(new_plan.risk),
                "tool_calls": [c.model_dump() for c in new_plan.tool_calls],
            },
        )
        current_plan = new_plan

    console.print("Agente> Parei para não entrar em loop. Se quiser, descreva o que você viu/obteve e eu continuo.")
    memory.append(
        "agent_response",
        {"text": "Parei para não entrar em loop. Se quiser, descreva o que você viu/obteve e eu continuo."},
    )
    return "Parei para não entrar em loop. Se quiser, descreva o que você viu/obteve e eu continuo."


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

    def self_coding_risk(tool_name: str, args: dict, settings: Settings | None) -> RiskLevel | None:
        if settings is None:
            return None
        if not getattr(settings, "self_coding_enabled", False):
            return None

        a = args or {}
        if tool_name == "write_file":
            p = str(a.get("path", "") or "").strip().replace("\\", "/")
            if p.startswith("scratch/") and p.lower().endswith(".py"):
                return RiskLevel.CRITICAL

        if tool_name == "dev.run_python":
            script = str(a.get("script", "") or "").strip().replace("\\", "/")
            if script.startswith("scratch/") and script.lower().endswith(".py"):
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

        dyn2 = self_coding_risk(call.tool_name, call.args, settings)
        if dyn2 is not None and rank(dyn2) > rank(tool_risk):
            tool_risk = dyn2

        if rank(tool_risk) > rank(current):
            current = tool_risk

    return current


def _preflight_validate_plan(plan: Plan, registry, *, settings: Settings | None = None) -> str | None:
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
        err = _preflight_validate_tool_call(call.tool_name, call.args, registry, settings=settings)
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


def _preflight_validate_tool_call(tool_name: str, args: dict, registry, settings: Settings | None = None) -> str | None:
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

        # Guardrail self-coding: escrita em scratch/ exige opt-in.
        if tool_name == "write_file":
            p = path.replace("\\", "/")
            if p.startswith("scratch/"):
                if settings is not None and not getattr(settings, "self_coding_enabled", False):
                    return "self-coding desabilitado (habilite OMNI_SELF_CODING_ENABLED=true)"

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

            # Guardrail self-coding: scripts em scratch/ exigem opt-in.
            if script.replace("\\", "/").startswith("scratch/"):
                if settings is not None and not getattr(settings, "self_coding_enabled", False):
                    return "self-coding desabilitado (habilite OMNI_SELF_CODING_ENABLED=true)"

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
