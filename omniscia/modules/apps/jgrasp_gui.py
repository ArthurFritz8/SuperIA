"""Automação simples do jGRASP via GUI.

Objetivo:
- Criar um arquivo Java funcional (HelloWorld) no workspace.
- Abrir esse arquivo no jGRASP via diálogo de "Open" (Ctrl+O).

Motivação:
- Sem integração por API, automação GUI precisa ser previsível.
- Criar o arquivo no disco é mais confiável do que depender de menus/estado do editor.

Limitações:
- Windows apenas (usa foco de janela + atalhos).
- Requer jGRASP aberto (o plano deve chamar os.open_app antes).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult
from omniscia.modules.os_control.win_windows import focus_window_by_title_contains


def register_jgrasp_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="jgrasp.create_java_program",
            description=(
                "Cria um arquivo .java funcional no workspace e abre no jGRASP (Ctrl+O). "
                "Args: path?, class_name?, message?, open_in_jgrasp?, settle_ms?"
            ),
            risk="HIGH",
            fn=_jgrasp_create_java_program,
        )
    )


def _require_pyautogui():
    try:
        import pyautogui

        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.05
        return pyautogui, None
    except Exception as exc:  # noqa: BLE001
        return None, f"pyautogui indisponível: {exc}"


def _safe_rel_java_path(path: str) -> Path:
    p = (path or "").strip().strip('"').strip("'").replace("\\", "/")
    if not p:
        raise ValueError("path vazio")
    if p.startswith("/") or ":" in p:
        raise ValueError("path deve ser relativo")
    if ".." in p.split("/"):
        raise ValueError("path não pode conter '..'")
    if not p.lower().endswith(".java"):
        raise ValueError("arquivo deve terminar com .java")
    return Path(p)


def _java_hello_world(class_name: str, message: str) -> str:
    cn = "".join(ch for ch in (class_name or "HelloWorld") if ch.isalnum() or ch == "_")
    if not cn or cn[0].isdigit():
        cn = "HelloWorld"
    msg = message or "Olá, mundo!"
    msg_escaped = msg.replace("\\", "\\\\").replace('"', '\\"')

    return (
        f"public class {cn} {{\n"
        "    public static void main(String[] args) {\n"
        f"        System.out.println(\"{msg_escaped}\");\n"
        "    }\n"
        "}\n"
    )


def _jgrasp_create_java_program(args: dict[str, Any]) -> ToolResult:
    if not sys.platform.startswith("win"):
        return ToolResult(status="error", error="jgrasp.create_java_program suporta apenas Windows")

    path_raw = str(args.get("path", "scratch/HelloWorld.java") or "scratch/HelloWorld.java")
    class_name = str(args.get("class_name", "HelloWorld") or "HelloWorld").strip()
    message = str(args.get("message", "Olá, mundo!") or "Olá, mundo!").strip()
    open_in_jgrasp = bool(args.get("open_in_jgrasp", True))
    settle_ms = int(args.get("settle_ms", 900) or 900)

    try:
        rel = _safe_rel_java_path(path_raw)
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))

    # Garanta que o nome da classe combina com o nome do arquivo quando possível.
    if rel.stem and (not class_name or class_name.lower() == "helloworld"):
        class_name = rel.stem

    code = _java_hello_world(class_name=class_name, message=message)

    try:
        abs_path = (Path.cwd() / rel).resolve()
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(code, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=f"falha ao criar arquivo: {exc}")

    if not open_in_jgrasp:
        return ToolResult(status="ok", output=f"created {rel.as_posix()}")

    pyautogui, err = _require_pyautogui()
    if pyautogui is None:
        return ToolResult(status="error", error=err)

    # Foca o jGRASP (mesmo se estiver minimizado / em outra tela).
    rect = focus_window_by_title_contains("jgrasp", timeout_s=3.0, visible_only=False)
    if not rect:
        # Alguns títulos aparecem como "jGRASP".
        rect = focus_window_by_title_contains("jgrasp", timeout_s=1.0, visible_only=False)
    if not rect:
        return ToolResult(status="error", error="janela do jGRASP não encontrada (abra o jGRASP primeiro)")

    time.sleep(max(0.0, float(settle_ms) / 1000.0))

    # Abre o diálogo de Open.
    pyautogui.hotkey("ctrl", "o")
    time.sleep(0.35)

    # Digita o caminho absoluto no campo de nome do arquivo e confirma.
    pyautogui.write(str(abs_path), interval=0.01)
    time.sleep(0.1)
    pyautogui.press("enter")
    time.sleep(0.45)

    return ToolResult(status="ok", output=f"created and opened {rel.as_posix()} in jGRASP")
