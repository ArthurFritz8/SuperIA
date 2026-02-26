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
import json

from omniscia.core.config import Settings

from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult


def register_open_tools(registry: ToolRegistry, settings: Settings | None = None) -> None:
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
            fn=lambda args: _os_open_app(args, settings=settings),
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

    # Browsers (podem depender de path; prefira configurar via OMNI_OPEN_APPS_*)
    "edge": "msedge.exe",
    "chrome": "chrome.exe",
    "firefox": "firefox.exe",

    # Dev / productivity (geralmente precisa configurar o path do exe)
    "vscode": "code",
    "code": "code",
    "notion": "notion://",

    # Media/games (via URL schemes quando possível)
    "steam": "steam://open/main",
    "spotify": "spotify:",
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
    "discord": "discord",
    "steam": "steam",
    "spotify": "spotify",
    "edge": "edge",
    "microsoft edge": "edge",
    "google chrome": "chrome",
    "chrome": "chrome",
    "mozilla firefox": "firefox",
    "firefox": "firefox",
    "vs code": "vscode",
    "visual studio code": "vscode",
}


_DENY_APP_KEYS = {
    "cmd",
    "commandprompt",
    "powershell",
    "pwsh",
    "terminal",
    "windows terminal",
    "regedit",
    "registry",
    "taskschd",
    "schtasks",
}

_DENY_TARGET_BASENAMES = {
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


def _load_extra_allow_apps(settings: Settings | None) -> dict[str, str]:
    if settings is None:
        return {}

    out: dict[str, str] = {}

    def _merge(mapping: dict[str, Any]) -> None:
        for k, v in (mapping or {}).items():
            key = str(k).strip().lower()
            if not key:
                continue
            out[key] = str(v).strip()

    # Inline JSON
    raw_json = (settings.open_apps_json or "").strip()
    if raw_json:
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, dict):
                _merge(parsed)
        except Exception:
            # Silent: keep tool usable even with bad config
            pass

    # JSON file (relative to workspace/cwd)
    raw_file = (settings.open_apps_file or "").strip()
    if raw_file:
        p = Path(raw_file)
        if not p.is_absolute():
            p = (Path.cwd() / p)
        try:
            if p.exists() and p.is_file():
                parsed = json.loads(p.read_text(encoding="utf-8", errors="replace"))
                if isinstance(parsed, dict):
                    _merge(parsed)
        except Exception:
            pass

    return out


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


def _os_open_app(args: dict[str, Any], *, settings: Settings | None = None) -> ToolResult:
    """Open a small set of allowlisted apps.

    This avoids using dev.exec for common desktop actions.
    """

    app_raw = str(args.get("app", "")).strip().lower()
    app = _APP_ALIASES.get(app_raw, app_raw)
    if not app:
        return ToolResult(status="error", error="app vazio")

    if app in _DENY_APP_KEYS:
        return ToolResult(status="error", error="app bloqueado por segurança")

    allow_apps = dict(_ALLOW_APPS)
    allow_apps.update(_load_extra_allow_apps(settings))

    if app not in allow_apps:
        allowed = ", ".join(sorted(allow_apps.keys()))
        return ToolResult(status="error", error=f"app não permitido. allowlist: {allowed}")

    if not sys.platform.startswith("win"):
        return ToolResult(status="error", error="os.open_app (MVP) suporta apenas Windows")

    try:
        target = str(allow_apps[app]).strip()
        if not target:
            return ToolResult(status="error", error="target vazio")

        base = os.path.basename(target).lower()
        if base in _DENY_TARGET_BASENAMES:
            return ToolResult(status="error", error="target bloqueado por segurança")

        # URL schemes / protocol handlers (discord://, steam://, spotify:)
        if "://" in target or target.endswith(":") or target.startswith("ms-settings:"):
            os.startfile(target)  # noqa: S606
            return ToolResult(status="ok", output=f"opened app {app}")

        # Absolute path to exe/lnk
        p = Path(target)
        if p.is_absolute():
            if not p.exists():
                return ToolResult(status="error", error=f"executável não existe: {p}")
            if p.suffix.lower() not in {".exe", ".lnk"}:
                return ToolResult(status="error", error="target deve ser .exe ou .lnk")
            subprocess.Popen([str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # noqa: S603,S607
            return ToolResult(status="ok", output=f"opened app {app}")

        subprocess.Popen([target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # noqa: S603,S607
        return ToolResult(status="ok", output=f"opened app {app}")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))
