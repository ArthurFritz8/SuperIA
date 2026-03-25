from __future__ import annotations

import logging
import re
import time
from dataclasses import replace
from typing import Any

from rich.console import Console
from rich.panel import Panel

from omniscia.core.config import Settings
from omniscia.modules.stt.factory import build_stt
from omniscia.modules.memory.store import JsonlMemoryStore

logger = logging.getLogger(__name__)


def handle_worker_commands(
    *,
    console: Console,
    user_message: str,
    worker_mgr,
) -> bool:
    """Handle local worker commands.

    Returns True if the message was handled and the caller should continue the REPL loop.
    """

    if worker_mgr is None:
        return False

    um = user_message.strip()
    if um.lower() in {"jobs", "job", "trabalhos"}:
        jobs = worker_mgr.list_jobs()
        if not jobs:
            console.print("Agente> Nenhum job em background.")
            return True
        lines = ["== Jobs =="]
        now = time.time()
        for j in jobs[-12:]:
            age = now - float(j.created_ts)
            lines.append(f"- {j.job_id} {j.name} status={j.status} age_s={age:.0f}")
        console.print(Panel("\n".join(lines), title="Workers"))
        return True

    mjob = re.fullmatch(r"job\s+([0-9a-fA-F]{6,12})", um.strip(), flags=re.IGNORECASE)
    if mjob:
        jid = mjob.group(1)
        info = worker_mgr.get_info(jid)
        if info is None:
            console.print("Agente> Job não encontrado.")
        else:
            console.print(
                Panel(
                    f"job_id={info.job_id}\nname={info.name}\nstatus={info.status}\ndone={info.done}",
                    title="Job",
                )
            )
        return True

    mcancel = re.fullmatch(r"cancel\s+([0-9a-fA-F]{6,12})", um.strip(), flags=re.IGNORECASE)
    if mcancel:
        jid = mcancel.group(1)
        ok = worker_mgr.cancel(jid)
        console.print(
            "Agente> "
            + (
                "Ok, tentei cancelar." if ok else "Não consegui cancelar (talvez já esteja rodando/finalizado)."
            )
        )
        return True

    return False


def recover_from_stt_error(
    *,
    console: Console,
    settings: Settings,
    exc: Exception,
):
    """Best-effort STT recovery: switch to text mode."""

    logger.exception("Falha no STT")
    console.print(f"[red]Erro no STT:[/red] {exc}")
    console.print("[yellow]Voltando para modo texto.[/yellow]")
    settings = replace(settings, stt_mode="text")
    stt = build_stt(settings, console=console)
    return settings, stt


def capture_hotkey_screen_context(
    *,
    console: Console,
    registry,
    memory: JsonlMemoryStore,
) -> tuple[str | None, str | None]:
    """Capture screen context (screenshot + OCR) after hotkey.

    Returns (image_path, ocr_text).
    """

    hotkey_image_path: str | None = None
    hotkey_ocr_text: str | None = None

    try:
        console.print("[dim]Capturando contexto de tela (hotkey)...[/dim]")
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

        memory.append(
            "screen_context",
            {
                "image_path": hotkey_image_path,
                "ocr": hotkey_ocr_text,
                "note": "Usuário acionou hotkey (Ctrl+Space) para ajuda contextual da tela.",
            },
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("Falha capturando contexto de tela")
        console.print(f"[yellow]Falha ao capturar tela:[/yellow] {e}")

    return hotkey_image_path, hotkey_ocr_text
