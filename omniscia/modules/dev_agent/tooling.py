"""Ferramentas (tools) do DevAgent.

Ferramentas expostas ao core:
- dev.exec: executa um comando allowlisted
- dev.run_python: executa `python -c` ou `python -m`

Rationale:
- Mantemos o core simples; as regras de execução ficam aqui.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult
from omniscia.modules.dev_agent.sandbox import parse_command, python_argv, run_command


def register_dev_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="dev.exec",
            description="Executa comando allowlisted (python/pytest/git) sem shell",
            risk="HIGH",
            fn=_dev_exec,
        )
    )

    registry.register(
        ToolSpec(
            name="dev.run_python",
            description="Executa Python do venv (-c, -m, ou script) de forma controlada",
            risk="HIGH",
            fn=_dev_run_python,
        )
    )


def _dev_exec(args: dict[str, Any]) -> ToolResult:
    command = str(args.get("command", "")).strip()
    timeout_s = float(args.get("timeout_s", 60.0) or 60.0)

    argv = parse_command(command)
    if not argv:
        return ToolResult(status="error", error="command vazio")

    try:
        res = run_command(argv=argv, cwd=Path("."), timeout_s=timeout_s)
        out = _format_exec(res)
        status = "ok" if res.exit_code == 0 else "error"
        return ToolResult(status=status, output=out, error=None if status == "ok" else "exit_code != 0")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _dev_run_python(args: dict[str, Any]) -> ToolResult:
    """Roda python do venv.

    Args:
- code: string para `-c`
- module: string para `-m`
- script: path relativo para script
- args: lista de args adicionais
    """

    timeout_s = float(args.get("timeout_s", 60.0) or 60.0)
    extra_args = args.get("args") or []
    if not isinstance(extra_args, list):
        extra_args = []

    if args.get("code"):
        argv = python_argv("-c", str(args.get("code")), *[str(a) for a in extra_args])
    elif args.get("module"):
        argv = python_argv("-m", str(args.get("module")), *[str(a) for a in extra_args])
    elif args.get("script"):
        script = str(args.get("script", "")).strip().replace("\\", "/")
        if not script or script.startswith("/") or ":" in script or ".." in script.split("/"):
            return ToolResult(status="error", error="script inválido (use path relativo) ")
        argv = python_argv(script, *[str(a) for a in extra_args])
    else:
        return ToolResult(status="error", error="informe code, module ou script")

    try:
        res = run_command(argv=argv, cwd=Path("."), timeout_s=timeout_s)
        out = _format_exec(res)
        status = "ok" if res.exit_code == 0 else "error"
        return ToolResult(status=status, output=out, error=None if status == "ok" else "exit_code != 0")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _format_exec(res) -> str:
    parts = [f"exit_code={res.exit_code} duration_s={res.duration_s:.2f}"]
    if res.stdout.strip():
        parts.append("--- stdout ---\n" + res.stdout.strip())
    if res.stderr.strip():
        parts.append("--- stderr ---\n" + res.stderr.strip())
    return "\n".join(parts)
