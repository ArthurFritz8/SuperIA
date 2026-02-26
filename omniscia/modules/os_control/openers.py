"""Ferramentas para abrir recursos no SO.

Objetivo:
- Evitar usar `dev.exec` para ações simples (abrir Explorer / abrir URL),
  mantendo guardrails e UX melhor.

Guardrails:
- URL: somente http/https.
- Explorer: path relativo dentro do workspace.
"""

from __future__ import annotations

import os
import sys
import webbrowser
import subprocess
from pathlib import Path
from typing import Any

from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult


def register_open_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="os.open_url",
            description="Abre uma URL (http/https) no navegador padrão",
            risk="MEDIUM",
            fn=_os_open_url,
        )
    )
    registry.register(
        ToolSpec(
            name="os.open_explorer",
            description="Abre o Explorador/Finder/gerenciador de arquivos no path informado (relativo)",
            risk="MEDIUM",
            fn=_os_open_explorer,
        )
    )

    registry.register(
        ToolSpec(
            name="os.open_app",
            description="Abre um app allowlisted no sistema (ex: calculator)",
            risk="MEDIUM",
            fn=_os_open_app,
        )
    )


_ALLOW_APPS = {
    # key -> windows executable
    "calculator": "calc.exe",
    "notepad": "notepad.exe",
    "paint": "mspaint.exe",
    "snippingtool": "snippingtool.exe",
    # Discord: melhor via URL scheme (não depende do PATH)
    "discord": "discord://",
}


_APP_ALIASES = {
    # PT-BR / common forms
    "calculadora": "calculator",
    "calc": "calculator",
    "bloco de notas": "notepad",
    "bloconotas": "notepad",
    "notas": "notepad",
    "paintbrush": "paint",
    "ferramenta de captura": "snippingtool",
    "captura": "snippingtool",
    "dc": "discord",
}


def _safe_rel_path(raw: str) -> Path:
    path = (raw or "").strip().replace("\\", "/")
    if not path:
        path = "."
    if path.startswith("~") or "/~" in path or "~" in path.split("/"):
        raise ValueError("path não pode usar '~' (use path relativo ao workspace)")
    if path.startswith("/") or ":" in path:
        raise ValueError("path deve ser relativo")

    p = Path(path)
    if any(part == ".." for part in p.parts):
        raise ValueError("path não pode conter '..'")

    # Resolve dentro do workspace atual (cwd)
    root = Path.cwd().resolve()
    resolved = (root / p).resolve()
    try:
        resolved.relative_to(root)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("path fora do workspace") from exc

    return resolved


def _os_open_url(args: dict[str, Any]) -> ToolResult:
    url = str(args.get("url", "")).strip()
    if not url:
        return ToolResult(status="error", error="url vazio")

    low = url.lower()
    if not (low.startswith("http://") or low.startswith("https://")):
        return ToolResult(status="error", error="url deve começar com http:// ou https://")

    try:
        ok = webbrowser.open(url, new=2)
        if not ok:
            return ToolResult(status="error", error="não consegui abrir o navegador")
        return ToolResult(status="ok", output=f"opened {url}")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _os_open_explorer(args: dict[str, Any]) -> ToolResult:
    raw = str(args.get("path", "."))
    try:
        target = _safe_rel_path(raw)
        if not target.exists() or not target.is_dir():
            return ToolResult(status="error", error="path não existe ou não é diretório")

        if sys.platform.startswith("win"):
            os.startfile(str(target))  # noqa: S606
            return ToolResult(status="ok", output=f"opened explorer at {target}")

        # macOS
        if sys.platform == "darwin":
            import subprocess

            subprocess.Popen(["open", str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # noqa: S603,S607
            return ToolResult(status="ok", output=f"opened file manager at {target}")

        # Linux / others
        import subprocess

        subprocess.Popen(["xdg-open", str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # noqa: S603,S607
        return ToolResult(status="ok", output=f"opened file manager at {target}")

    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _os_open_app(args: dict[str, Any]) -> ToolResult:
    """Open a small set of allowlisted apps.

    This avoids using dev.exec for common desktop actions.
    """

    app_raw = str(args.get("app", "")).strip().lower()
    app = _APP_ALIASES.get(app_raw, app_raw)
    if not app:
        return ToolResult(status="error", error="app vazio")

    if app not in _ALLOW_APPS:
        allowed = ", ".join(sorted(_ALLOW_APPS.keys()))
        return ToolResult(status="error", error=f"app não permitido. allowlist: {allowed}")

    if not sys.platform.startswith("win"):
        return ToolResult(status="error", error="os.open_app (MVP) suporta apenas Windows")

    try:
        target = _ALLOW_APPS[app]
        if "://" in target:
            os.startfile(target)  # noqa: S606
            return ToolResult(status="ok", output=f"opened app {app}")

        subprocess.Popen([target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # noqa: S603,S607
        return ToolResult(status="ok", output=f"opened app {app}")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))
