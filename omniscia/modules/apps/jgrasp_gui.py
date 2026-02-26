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
import re
from typing import Any

from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult
from omniscia.modules.os_control.filesystem import _safe_abs_windows_path, _safe_rel_subpath, _win_known_folder
from omniscia.modules.os_control.win_windows import (
    find_window_hwnd_by_title_contains,
    focus_window_by_title_contains,
    get_foreground_window_hwnd,
    get_foreground_window_title,
)


def register_jgrasp_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="jgrasp.create_java_program",
            description=(
                "Cria um arquivo .java funcional e abre no jGRASP (Ctrl+O). "
                "Por padrão, cria no workspace (path relativo). Também aceita path com prefixo "
                "desktop:/..., documents:/..., downloads:/... ou path absoluto (com guardrails). "
                "Args: path?, class_name?, message?, code?, open_in_jgrasp?, settle_ms?"
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


def _safe_abs_windows_java_target(raw: str, class_name: str) -> Path:
    """Resolve a safe target path for .java using Windows absolute paths.

    Accepts:
    - Absolute directory path (creates <ClassName>.java inside)
    - Absolute .java file path

    Guardrails:
    - Blocks system directories (Windows/Program Files)
    - Blocks drive root (e.g. D:\\)
    """

    s = (raw or "").strip().strip('"').strip("'").replace("/", "\\")
    if not s:
        raise ValueError("path vazio")
    p = Path(s)
    if not p.is_absolute() or ":" not in s[:3]:
        raise ValueError("path deve ser absoluto (ex: C:\\Users\\...\\Desktop)")
    if any(part == ".." for part in p.parts):
        raise ValueError("path não pode conter '..'")

    resolved = p.resolve()

    # If it is a directory (or looks like one), create file inside it.
    if resolved.exists() and resolved.is_dir():
        safe_cn = "".join(ch for ch in (class_name or "HelloWorld") if ch.isalnum() or ch == "_")
        if not safe_cn or safe_cn[0].isdigit():
            safe_cn = "HelloWorld"
        # Validate the directory target itself.
        _safe_abs_windows_path(str(resolved))
        return (resolved / f"{safe_cn}.java").resolve()

    # If not existing: infer directory vs file by suffix.
    if str(resolved).lower().endswith(".java"):
        # Validate parent directory.
        _safe_abs_windows_path(str(resolved.parent))
        return resolved

    # Treat as directory path even if it doesn't exist yet.
    safe_cn = "".join(ch for ch in (class_name or "HelloWorld") if ch.isalnum() or ch == "_")
    if not safe_cn or safe_cn[0].isdigit():
        safe_cn = "HelloWorld"
    # Validate the (possibly non-existent) directory path.
    _safe_abs_windows_path(str(resolved))
    return (resolved / f"{safe_cn}.java").resolve()


def _resolve_java_target(path_raw: str, class_name: str) -> tuple[Path, str]:
    """Return (absolute_path, display_path).

    display_path is relative when inside workspace; otherwise absolute.
    """

    raw = str(path_raw or "").strip()

    # Prefix form: desktop:/..., documents:/..., downloads:/...
    low = raw.lower().strip().replace("\\", "/")
    if low.startswith(("desktop:", "documents:", "downloads:")):
        prefix, rest = low.split(":", 1)
        base = _win_known_folder(prefix)
        sub = _safe_rel_subpath(rest)
        # Must be a .java file path
        if not str(sub).lower().endswith(".java"):
            raise ValueError("arquivo deve terminar com .java")
        abs_path = (base / sub).resolve()
        return abs_path, str(abs_path)

    # Absolute Windows path form
    if ":" in raw[:3] or raw.startswith("\\"):
        abs_path = _safe_abs_windows_java_target(raw, class_name=class_name)
        return abs_path, str(abs_path)

    # Workspace-relative (default)
    rel = _safe_rel_java_path(raw or "scratch/HelloWorld.java")
    abs_path = (Path.cwd() / rel).resolve()
    return abs_path, rel.as_posix()


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


def _sanitize_java_class_name(raw: str, *, fallback: str = "HelloWorld") -> str:
    cn = "".join(ch for ch in (raw or "") if ch.isalnum() or ch == "_")
    if not cn or cn[0].isdigit():
        return fallback
    return cn


def _looks_like_java_source(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    # Heurística: o LLM às vezes manda o código inteiro em `message`.
    if "\n" not in t and "\r" not in t:
        return False
    if not re.search(r"\bclass\b", t):
        return False
    if not re.search(r"\bstatic\s+void\s+main\b", t):
        return False
    return True


def _java_matrix_demo(class_name: str) -> str:
    cn = _sanitize_java_class_name(class_name, fallback="Matriz")
    return (
        f"public class {cn} {{\n"
        "    public static void main(String[] args) {\n"
        "        int linhas = 3;\n"
        "        int colunas = 3;\n"
        "        int[][] matriz = new int[linhas][colunas];\n\n"
        "        // Preenche com um padrão simples\n"
        "        for (int i = 0; i < linhas; i++) {\n"
        "            for (int j = 0; j < colunas; j++) {\n"
        "                matriz[i][j] = (i + 1) * (j + 1);\n"
        "            }\n"
        "        }\n\n"
        "        // Imprime a matriz\n"
        "        System.out.println(\"Matriz 3x3:\");\n"
        "        for (int i = 0; i < linhas; i++) {\n"
        "            for (int j = 0; j < colunas; j++) {\n"
        "                System.out.print(matriz[i][j] + \"\\t\");\n"
        "            }\n"
        "            System.out.println();\n"
        "        }\n\n"
        "        // Soma dos elementos\n"
        "        int soma = 0;\n"
        "        for (int i = 0; i < linhas; i++) {\n"
        "            for (int j = 0; j < colunas; j++) {\n"
        "                soma += matriz[i][j];\n"
        "            }\n"
        "        }\n"
        "        System.out.println(\"Soma = \" + soma);\n"
        "    }\n"
        "}\n"
    )


def _jgrasp_create_java_program(args: dict[str, Any]) -> ToolResult:
    if not sys.platform.startswith("win"):
        return ToolResult(status="error", error="jgrasp.create_java_program suporta apenas Windows")

    class_name = str(args.get("class_name", "HelloWorld") or "HelloWorld").strip()
    class_name = _sanitize_java_class_name(class_name, fallback="HelloWorld")

    # Se path não vier, derive do nome da classe (melhor que sempre HelloWorld.java).
    path_raw = str(args.get("path", "") or "").strip()
    if not path_raw:
        path_raw = f"scratch/{class_name}.java"

    message = str(args.get("message", "Olá, mundo!") or "Olá, mundo!")
    raw_code = args.get("code")
    code_arg = str(raw_code) if raw_code is not None else ""

    open_in_jgrasp = bool(args.get("open_in_jgrasp", True))
    settle_ms = int(args.get("settle_ms", 900) or 900)

    try:
        abs_path, display_path = _resolve_java_target(path_raw, class_name=class_name)
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))

    # Garanta que o nome da classe combina com o nome do arquivo quando possível.
    if abs_path.stem and (not class_name or class_name.lower() == "helloworld"):
        class_name = _sanitize_java_class_name(abs_path.stem, fallback="HelloWorld")

    # Conteúdo do arquivo:
    # - Preferir `code` quando fornecido
    # - Se `message` parece código Java, tratar como `code` (compatibilidade com planos antigos/LLM)
    # - Caso contrário, gerar HelloWorld imprimindo `message`
    code: str
    if code_arg.strip():
        code = code_arg
    elif _looks_like_java_source(message):
        code = message
    else:
        code = _java_hello_world(class_name=class_name, message=str(message).strip())

    if not code.endswith("\n"):
        code += "\n"

    try:
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(code, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=f"falha ao criar arquivo: {exc}")

    if not open_in_jgrasp:
        return ToolResult(status="ok", output=f"created {display_path}")

    pyautogui, err = _require_pyautogui()
    if pyautogui is None:
        return ToolResult(status="error", error=err)

    # Foca o jGRASP (mesmo se estiver minimizado / em outra tela).
    jgrasp_hwnd = find_window_hwnd_by_title_contains("jgrasp", timeout_s=2.0, visible_only=False)
    rect = focus_window_by_title_contains("jgrasp", timeout_s=3.0, visible_only=False)
    if not rect:
        # Alguns títulos aparecem como "jGRASP".
        rect = focus_window_by_title_contains("jgrasp", timeout_s=1.0, visible_only=False)
    if not rect:
        return ToolResult(status="error", error="janela do jGRASP não encontrada (abra o jGRASP primeiro)")

    time.sleep(max(0.0, float(settle_ms) / 1000.0))

    # Abre o diálogo de Open.
    # Às vezes o título do diálogo não é literalmente "Open/Abrir" (Swing/JFileChooser),
    # então validamos pelo foreground HWND/título e tentamos 2x.
    open_keywords = [
        "open",
        "abrir",
        "arquivo",
        "file",
        "selecionar",
        "choose",
        "escolher",
    ]

    def _dialog_is_foreground() -> bool:
        fg_hwnd = get_foreground_window_hwnd()
        fg_title = (get_foreground_window_title() or "").strip()
        fg_cf = fg_title.casefold()

        # If foreground is not the main jGRASP window, it's very likely the dialog.
        if jgrasp_hwnd and fg_hwnd and int(fg_hwnd) != int(jgrasp_hwnd):
            return True

        # Otherwise rely on title keywords.
        return any(k in fg_cf for k in open_keywords)

    dialog_ok = False
    for _ in range(2):
        pyautogui.hotkey("ctrl", "o")
        # Give it time to appear.
        deadline = time.time() + 2.0
        while time.time() < deadline:
            if _dialog_is_foreground():
                dialog_ok = True
                break
            time.sleep(0.05)
        if dialog_ok:
            break
        time.sleep(0.15)

    if not dialog_ok:
        return ToolResult(
            status="error",
            error=(
                "diálogo de Abrir não detectado após Ctrl+O; "
                f"arquivo foi criado em {display_path}. "
                "Abra manualmente no jGRASP (Ctrl+O) e cole o caminho."
            ),
        )

    time.sleep(0.1)
    pyautogui.hotkey("ctrl", "a")
    time.sleep(0.05)
    pyautogui.write(str(abs_path), interval=0.01)
    time.sleep(0.1)
    pyautogui.press("enter")
    time.sleep(0.45)

    return ToolResult(status="ok", output=f"created and opened {display_path} in jGRASP")
