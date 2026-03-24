"""Tools para controlar o VS Code via CLI (`code`).

Objetivo:
- Operar VS Code de forma confiável (preferir CLI/config a automação de tela).

Guardrails:
- Operações de arquivo são relativas ao workspace.
- Edição apenas em arquivos do workspace (ex.: .vscode/settings.json).
- Se `code` não existir no PATH, retorna erro claro.

Obs:
- Em Windows, pode ser necessário habilitar o comando `code` no PATH.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult


def register_vscode_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="vscode.open",
            description="Abre o VS Code (workspace atual ou path). Args: path? (relativo)",
            risk="MEDIUM",
            fn=_vscode_open,
        )
    )

    registry.register(
        ToolSpec(
            name="vscode.open_file",
            description="Abre um arquivo no VS Code (go to line). Args: path, line?, column? (relativo)",
            risk="MEDIUM",
            fn=_vscode_open_file,
        )
    )

    registry.register(
        ToolSpec(
            name="vscode.list_extensions",
            description="Lista extensões instaladas no VS Code. Args: show_versions?",
            risk="LOW",
            fn=_vscode_list_extensions,
        )
    )

    registry.register(
        ToolSpec(
            name="vscode.install_extension",
            description="Instala uma extensão pelo id. Args: extension_id, force?",
            risk="HIGH",
            fn=_vscode_install_extension,
        )
    )

    registry.register(
        ToolSpec(
            name="vscode.uninstall_extension",
            description="Remove uma extensão pelo id. Args: extension_id",
            risk="HIGH",
            fn=_vscode_uninstall_extension,
        )
    )

    registry.register(
        ToolSpec(
            name="vscode.settings_read",
            description="Lê .vscode/settings.json (workspace).",
            risk="LOW",
            fn=_vscode_settings_read,
        )
    )

    registry.register(
        ToolSpec(
            name="vscode.settings_get",
            description="Obtém um valor em .vscode/settings.json. Args: key",
            risk="LOW",
            fn=_vscode_settings_get,
        )
    )

    registry.register(
        ToolSpec(
            name="vscode.settings_update",
            description="Atualiza .vscode/settings.json via merge patch. Args: patch (dict)",
            risk="HIGH",
            fn=_vscode_settings_update,
        )
    )

    registry.register(
        ToolSpec(
            name="vscode.extensions_read",
            description="Lê .vscode/extensions.json (recomendações).",
            risk="LOW",
            fn=_vscode_extensions_read,
        )
    )

    registry.register(
        ToolSpec(
            name="vscode.extensions_update",
            description=(
                "Atualiza .vscode/extensions.json (recomendações). Args: add?, remove? (listas de ids)"
            ),
            risk="HIGH",
            fn=_vscode_extensions_update,
        )
    )

    registry.register(
        ToolSpec(
            name="vscode.tasks_read",
            description="Lê .vscode/tasks.json (workspace).",
            risk="LOW",
            fn=_vscode_tasks_read,
        )
    )

    registry.register(
        ToolSpec(
            name="vscode.tasks_update",
            description="Atualiza .vscode/tasks.json via merge patch. Args: patch (dict)",
            risk="HIGH",
            fn=_vscode_tasks_update,
        )
    )

    registry.register(
        ToolSpec(
            name="vscode.launch_read",
            description="Lê .vscode/launch.json (workspace).",
            risk="LOW",
            fn=_vscode_launch_read,
        )
    )

    registry.register(
        ToolSpec(
            name="vscode.launch_update",
            description="Atualiza .vscode/launch.json via merge patch. Args: patch (dict)",
            risk="HIGH",
            fn=_vscode_launch_update,
        )
    )


def _safe_rel_path(raw: str) -> Path:
    path = (raw or "").strip().strip('"').strip("'").replace("\\", "/")
    if not path:
        path = "."
    if path.startswith("/") or ":" in path:
        raise ValueError("path deve ser relativo ao workspace")
    if ".." in Path(path).parts:
        raise ValueError("path não pode conter '..'")

    root = Path.cwd().resolve()
    resolved = (root / Path(path)).resolve()
    resolved.relative_to(root)
    return resolved


def _require_code_cli() -> tuple[bool, str | None]:
    try:
        res = subprocess.run(["code", "--version"], capture_output=True, text=True, timeout=4, check=False)
        if res.returncode != 0:
            return False, "comando 'code' não está disponível (VS Code CLI)."
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, f"comando 'code' indisponível: {exc}"


def _vscode_open(args: dict[str, Any]) -> ToolResult:
    ok, err = _require_code_cli()
    if not ok:
        return ToolResult(
            status="error",
            error=(
                (err or "VS Code CLI indisponível")
                + " Dica: no VS Code, execute 'Shell Command: Install \'code\' command in PATH' (ou reinstale marcando Add to PATH)."
            ),
        )

    raw = str(args.get("path", ".") or ".")
    try:
        target = _safe_rel_path(raw)
        subprocess.Popen(["code", str(target)])
        rel = str(target.relative_to(Path.cwd().resolve())).replace("\\", "/")
        return ToolResult(status="ok", output=f"opened vscode at {rel}")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _vscode_open_file(args: dict[str, Any]) -> ToolResult:
    ok, err = _require_code_cli()
    if not ok:
        return ToolResult(status="error", error=err or "VS Code CLI indisponível")

    raw = str(args.get("path", "") or "").strip()
    if not raw:
        return ToolResult(status="error", error="path vazio")

    line = int(args.get("line", 1) or 1)
    col = int(args.get("column", 1) or 1)
    if line < 1:
        line = 1
    if col < 1:
        col = 1

    try:
        p = _safe_rel_path(raw)
        if not p.exists() or not p.is_file():
            return ToolResult(status="error", error="arquivo não existe")
        loc = f"{str(p)}:{line}:{col}"
        subprocess.Popen(["code", "-g", loc])
        rel = str(p.relative_to(Path.cwd().resolve())).replace("\\", "/")
        return ToolResult(status="ok", output=f"opened {rel} at {line}:{col}")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _vscode_list_extensions(args: dict[str, Any]) -> ToolResult:
    ok, err = _require_code_cli()
    if not ok:
        return ToolResult(status="error", error=err or "VS Code CLI indisponível")

    show_versions = bool(args.get("show_versions", True))
    cmd = ["code", "--list-extensions"]
    if show_versions:
        cmd.append("--show-versions")

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)
        out = (res.stdout or "").strip()
        if res.returncode != 0 and not out:
            return ToolResult(status="error", error=(res.stderr or "falha listando extensões"))
        return ToolResult(status="ok", output=out or "")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _valid_extension_id(ext: str) -> bool:
    t = (ext or "").strip()
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9\-]*\.[A-Za-z0-9][A-Za-z0-9\-\.]*", t))


def _vscode_install_extension(args: dict[str, Any]) -> ToolResult:
    ok, err = _require_code_cli()
    if not ok:
        return ToolResult(status="error", error=err or "VS Code CLI indisponível")

    ext = str(args.get("extension_id", "") or "").strip()
    if not _valid_extension_id(ext):
        return ToolResult(status="error", error="extension_id inválido (ex: ms-python.python)")

    force = bool(args.get("force", False))
    cmd = ["code", "--install-extension", ext]
    if force:
        cmd.append("--force")

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
        if res.returncode != 0:
            return ToolResult(status="error", error=(res.stderr or res.stdout or "falha instalando extensão"))
        return ToolResult(status="ok", output=(res.stdout or "installed"))
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _vscode_uninstall_extension(args: dict[str, Any]) -> ToolResult:
    ok, err = _require_code_cli()
    if not ok:
        return ToolResult(status="error", error=err or "VS Code CLI indisponível")

    ext = str(args.get("extension_id", "") or "").strip()
    if not _valid_extension_id(ext):
        return ToolResult(status="error", error="extension_id inválido (ex: ms-python.python)")

    cmd = ["code", "--uninstall-extension", ext]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
        if res.returncode != 0:
            return ToolResult(status="error", error=(res.stderr or res.stdout or "falha removendo extensão"))
        return ToolResult(status="ok", output=(res.stdout or "uninstalled"))
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        raw = path.read_text(encoding="utf-8", errors="replace")
        data = json.loads(raw) if raw.strip() else {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_json_file(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _vscode_settings_path() -> Path:
    return _safe_rel_path(".vscode/settings.json")


def _vscode_extensions_path() -> Path:
    return _safe_rel_path(".vscode/extensions.json")


def _vscode_tasks_path() -> Path:
    return _safe_rel_path(".vscode/tasks.json")


def _vscode_launch_path() -> Path:
    return _safe_rel_path(".vscode/launch.json")


def _vscode_settings_read(args: dict[str, Any]) -> ToolResult:
    try:
        p = _vscode_settings_path()
        data = _read_json_file(p)
        return ToolResult(status="ok", output=json.dumps(data, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _vscode_settings_get(args: dict[str, Any]) -> ToolResult:
    key = str(args.get("key", "") or "").strip()
    if not key:
        return ToolResult(status="error", error="key vazio")

    try:
        p = _vscode_settings_path()
        data = _read_json_file(p)
        value = data.get(key)
        return ToolResult(status="ok", output=json.dumps({"key": key, "value": value}, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _merge_patch(dst: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(dst)
    for k, v in (patch or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge_patch(out.get(k, {}), v)
        else:
            out[k] = v
    return out


def _vscode_settings_update(args: dict[str, Any]) -> ToolResult:
    patch = args.get("patch")
    if not isinstance(patch, dict):
        return ToolResult(status="error", error="patch deve ser um dict")

    try:
        p = _vscode_settings_path()
        cur = _read_json_file(p)
        merged = _merge_patch(cur, patch)
        _write_json_file(p, merged)
        return ToolResult(status="ok", output="updated .vscode/settings.json")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _vscode_extensions_read(args: dict[str, Any]) -> ToolResult:
    try:
        p = _vscode_extensions_path()
        data = _read_json_file(p)
        return ToolResult(status="ok", output=json.dumps(data, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _vscode_extensions_update(args: dict[str, Any]) -> ToolResult:
    add = args.get("add")
    remove = args.get("remove")

    add_list = [str(x).strip() for x in (add or [])] if isinstance(add, list) else []
    remove_list = [str(x).strip() for x in (remove or [])] if isinstance(remove, list) else []

    # Validate ids best-effort.
    add_list = [x for x in add_list if _valid_extension_id(x)]
    remove_list = [x for x in remove_list if _valid_extension_id(x)]

    try:
        p = _vscode_extensions_path()
        cur = _read_json_file(p)
        recs = cur.get("recommendations")
        rec_list = [str(x).strip() for x in recs] if isinstance(recs, list) else []

        s = {x for x in rec_list if x}
        for x in add_list:
            s.add(x)
        for x in remove_list:
            s.discard(x)

        cur["recommendations"] = sorted(s, key=lambda t: t.casefold())
        _write_json_file(p, cur)
        return ToolResult(status="ok", output="updated .vscode/extensions.json")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _vscode_tasks_read(args: dict[str, Any]) -> ToolResult:
    try:
        p = _vscode_tasks_path()
        data = _read_json_file(p)
        return ToolResult(status="ok", output=json.dumps(data, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _vscode_tasks_update(args: dict[str, Any]) -> ToolResult:
    patch = args.get("patch")
    if not isinstance(patch, dict):
        return ToolResult(status="error", error="patch deve ser um dict")

    try:
        p = _vscode_tasks_path()
        cur = _read_json_file(p)
        merged = _merge_patch(cur, patch)
        _write_json_file(p, merged)
        return ToolResult(status="ok", output="updated .vscode/tasks.json")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _vscode_launch_read(args: dict[str, Any]) -> ToolResult:
    try:
        p = _vscode_launch_path()
        data = _read_json_file(p)
        return ToolResult(status="ok", output=json.dumps(data, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _vscode_launch_update(args: dict[str, Any]) -> ToolResult:
    patch = args.get("patch")
    if not isinstance(patch, dict):
        return ToolResult(status="error", error="patch deve ser um dict")

    try:
        p = _vscode_launch_path()
        cur = _read_json_file(p)
        merged = _merge_patch(cur, patch)
        _write_json_file(p, merged)
        return ToolResult(status="ok", output="updated .vscode/launch.json")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))
