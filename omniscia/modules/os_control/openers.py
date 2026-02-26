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
import re
import unicodedata

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

    registry.register(
        ToolSpec(
            name="os.scan_apps",
            description=(
                "Lista atalhos de apps no Windows (Menu Iniciar/Desktop) para ajudar a montar a allowlist. "
                "Retorna JSON com {key,name,target}."
            ),
            risk="LOW",
            fn=_os_scan_apps,
        )
    )

    registry.register(
        ToolSpec(
            name="os.generate_open_apps",
            description=(
                "Gera um JSON (app->target) no workspace a partir dos atalhos do Windows, "
                "para usar em OMNI_OPEN_APPS_FILE."
            ),
            risk="HIGH",
            fn=_os_generate_open_apps,
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


def _slug_key(name: str) -> str:
    """Convert shortcut/app names into stable keys for JSON mapping."""

    t = (name or "").strip().lower()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = re.sub(r"[^a-z0-9]+", "_", t).strip("_")
    return t or "app"


def _safe_rel_json_path(raw: str) -> Path:
    """Workspace-relative path for generated JSON files."""

    path = (raw or "").strip().strip('"').strip("'").replace("\\", "/")
    if not path:
        raise ValueError("out_path vazio")
    if path.startswith("/") or ":" in path:
        raise ValueError("out_path deve ser relativo")
    if path.startswith("~") or "/~" in path or "~" in path.split("/"):
        raise ValueError("out_path não pode usar '~'")
    if ".." in path.split("/"):
        raise ValueError("out_path não pode conter '..'")
    if not path.lower().endswith(".json"):
        raise ValueError("out_path deve terminar com .json")

    root = Path.cwd().resolve()
    resolved = (root / Path(path)).resolve()
    try:
        resolved.relative_to(root)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("out_path fora do workspace") from exc

    return resolved


def _win_shortcut_dirs() -> list[Path]:
    """Start Menu + Desktop locations (not OneDrive-specific; shortcuts still work)."""

    if not sys.platform.startswith("win"):
        return []

    dirs: list[Path] = []
    program_data = os.environ.get("PROGRAMDATA") or "C:/ProgramData"
    app_data = os.environ.get("APPDATA")
    user_profile = os.environ.get("USERPROFILE")

    dirs.append(Path(program_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    if app_data:
        dirs.append(Path(app_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    if user_profile:
        dirs.append(Path(user_profile) / "Desktop")

    # Dedup + filter existing
    out: list[Path] = []
    seen: set[str] = set()
    for d in dirs:
        p = Path(str(d))
        key = str(p).lower()
        if key in seen:
            continue
        seen.add(key)
        if p.exists() and p.is_dir():
            out.append(p)
    return out


def _collect_shortcuts(*, max_results: int = 600) -> list[dict[str, str]]:
    """Collect .lnk shortcuts and produce suggested mapping entries."""

    results: list[dict[str, str]] = []
    if not sys.platform.startswith("win"):
        return results

    for base in _win_shortcut_dirs():
        for p in base.rglob("*.lnk"):
            if len(results) >= max_results:
                return results
            try:
                name = p.stem
                key = _slug_key(name)
                # Keep it as forward-slash path in JSON for readability.
                target = str(p.resolve()).replace("\\", "/")

                # Skip blocked targets by basename (best-effort).
                if os.path.basename(target).lower() in _DENY_TARGET_BASENAMES:
                    continue
                if key in _DENY_APP_KEYS:
                    continue

                results.append({"key": key, "name": name, "target": target})
            except Exception:
                continue

    return results


def _os_scan_apps(args: dict[str, Any]) -> ToolResult:
    """List Windows shortcut apps for allowlist building."""

    max_results = int(args.get("max_results", 600) or 600)
    if max_results < 1:
        max_results = 1
    if max_results > 2000:
        max_results = 2000

    if not sys.platform.startswith("win"):
        payload = {"apps": [], "count": 0, "note": "os.scan_apps só tem resultado no Windows"}
        return ToolResult(status="ok", output=json.dumps(payload, ensure_ascii=False))

    apps = _collect_shortcuts(max_results=max_results)
    payload = {"apps": apps, "count": len(apps), "dirs": [str(p) for p in _win_shortcut_dirs()]}
    return ToolResult(status="ok", output=json.dumps(payload, ensure_ascii=False))


def _os_generate_open_apps(args: dict[str, Any]) -> ToolResult:
    """Generate a mapping JSON in the workspace for OMNI_OPEN_APPS_FILE."""

    out_path_raw = str(args.get("out_path", "data/open_apps.generated.json") or "").strip()
    max_apps = int(args.get("max_apps", 350) or 350)
    overwrite = bool(args.get("overwrite", False))

    try:
        out_path = _safe_rel_json_path(out_path_raw)
        if out_path.exists() and not overwrite:
            return ToolResult(status="error", error="out_path já existe (use overwrite=true)")

        if not sys.platform.startswith("win"):
            return ToolResult(status="error", error="os.generate_open_apps só é suportado no Windows")

        apps = _collect_shortcuts(max_results=max_apps)
        mapping: dict[str, str] = {}
        used: set[str] = set()
        for item in apps:
            key = str(item.get("key") or "").strip().lower()
            target = str(item.get("target") or "").strip()
            if not key or not target:
                continue
            base = key
            i = 2
            while key in used:
                key = f"{base}_{i}"
                i += 1
            used.add(key)
            mapping[key] = target

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
        rel = str(out_path.relative_to(Path.cwd().resolve())).replace("\\", "/")
        return ToolResult(status="ok", output=f"generated {rel} (apps={len(mapping)})")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


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
