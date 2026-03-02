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
from omniscia.modules.dev_agent.autofix import autofix_python_file
from omniscia.modules.dev_agent.autofix_cmd import autofix_command
from omniscia.modules.dev_agent.scaffold import scaffold_python_project

# Import leve: Settings vem do core e não puxa dependências pesadas.
from omniscia.core.config import Settings


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

    registry.register(
        ToolSpec(
            name="dev.autofix_python_file",
            description="Roda um arquivo Python e tenta auto-corrigir via LLM (opcional)",
            risk="HIGH",
            fn=_dev_autofix_python_file,
        )
    )

    registry.register(
        ToolSpec(
            name="dev.autofix_cmd",
            description="Roda um comando (ex: pytest) e tenta auto-corrigir via LLM (opcional)",
            risk="HIGH",
            fn=_dev_autofix_cmd,
        )
    )

    registry.register(
        ToolSpec(
            name="dev.scaffold_project",
            description="Cria um projeto Python minimalista (src layout + pytest) no workspace",
            risk="HIGH",
            fn=scaffold_python_project,
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


def _dev_autofix_python_file(args: dict[str, Any]) -> ToolResult:
    path = str(args.get("path", "")).strip()
    max_iters = int(args.get("max_iters", 3) or 3)
    timeout_s = float(args.get("timeout_s", 60.0) or 60.0)

    if not path:
        return ToolResult(status="error", error="informe path")

    settings = Settings.load()
    res = autofix_python_file(settings=settings, path=path, max_iters=max_iters, timeout_s=timeout_s)

    if res.status == "ok":
        return ToolResult(status="ok", output=f"autofix ok in {res.iters} iter(s): {res.summary}")
    if res.status == "needs_llm":
        return ToolResult(status="error", error=res.summary)

    return ToolResult(status="error", error=f"autofix failed after {res.iters} iter(s): {res.summary}")


def _dev_autofix_cmd(args: dict[str, Any]) -> ToolResult:
    command = str(args.get("command", "")).strip()
    max_iters = int(args.get("max_iters", 3) or 3)
    timeout_s = float(args.get("timeout_s", 120.0) or 120.0)

    if not command:
        return ToolResult(status="error", error="informe command")

    settings = Settings.load()
    res = autofix_command(settings=settings, command=command, max_iters=max_iters, timeout_s=timeout_s)

    if res.status == "ok":
        return ToolResult(status="ok", output=f"autofix ok in {res.iters} iter(s): {res.summary}")
    if res.status == "needs_llm":
        return ToolResult(status="error", error=res.summary)

    return ToolResult(status="error", error=f"autofix failed after {res.iters} iter(s): {res.summary}")
