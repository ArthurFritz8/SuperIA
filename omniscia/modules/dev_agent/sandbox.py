"""Sandbox de execução de comandos.

Rationale:
- Um agente autônomo precisa rodar código/testes para fechar o loop (plan->exec->fix).
- Porém `subprocess` é uma porta direta para ações destrutivas.

Guardrails implementados aqui:
- Sem `shell=True` (evita injeções via shell)
- Working directory controlado (workspace atual)
- Allowlist de executáveis (começamos conservadores)
- Timeout
- Truncamento de stdout/stderr para evitar flood

Importante:
- Este sandbox não substitui HITL. HITL deve ser aplicado no core antes do side-effect.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float


def parse_command(command: str) -> list[str]:
    """Parseia uma string de comando em argv.

    Observação:
- Preferimos `shlex.split` por simplicidade.
- Em Windows, parsing perfeito de cmd.exe é complexo; como usamos sem shell,
  a maioria dos casos de `python -c "..."` funciona bem com aspas.
    """

    command = (command or "").strip()
    if not command:
        return []

    return shlex.split(command, posix=os.name != "nt")


def is_allowlisted(argv: list[str]) -> bool:
    """Decide se o executável está allowlisted.

    Começamos conservadores para reduzir riscos no MVP.
    """

    if not argv:
        return False

    exe = argv[0].lower().replace("\\", "/")

    # Permite chamar o python do venv explicitamente ou via 'python'.
    if exe.endswith("python") or exe.endswith("python.exe") or exe == "python":
        return True

    # Permite pytest (quando instalado) e git (para fluxo de dev).
    if exe.endswith("pytest") or exe.endswith("pytest.exe") or exe == "pytest":
        return True

    if exe.endswith("git") or exe.endswith("git.exe") or exe == "git":
        return True

    return False


def run_command(
    *,
    argv: list[str],
    cwd: str | Path = ".",
    timeout_s: float = 60.0,
    max_output_chars: int = 3500,
    env: dict[str, str] | None = None,
) -> ExecResult:
    """Executa argv e retorna stdout/stderr.

    Segurança:
    - `argv` não deve ser vazio.
    - `argv[0]` deve estar allowlisted.
    """

    if not argv:
        raise ValueError("argv vazio")

    if not is_allowlisted(argv):
        raise PermissionError(f"Executável não allowlisted: {argv[0]}")

    cwd_path = Path(cwd)
    if not cwd_path.exists():
        raise ValueError("cwd não existe")

    # Env controlado: herdamos, mas podemos sobrescrever.
    final_env = dict(os.environ)
    if env:
        final_env.update(env)

    start = time.time()
    proc = subprocess.run(
        argv,
        cwd=str(cwd_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_s,
        shell=False,
    )
    dur = time.time() - start

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""

    if len(stdout) > max_output_chars:
        stdout = stdout[:max_output_chars] + "\n... [stdout truncado]"
    if len(stderr) > max_output_chars:
        stderr = stderr[:max_output_chars] + "\n... [stderr truncado]"

    return ExecResult(exit_code=int(proc.returncode), stdout=stdout, stderr=stderr, duration_s=dur)


def python_argv(*args: str) -> list[str]:
    """Retorna argv usando o mesmo python do processo atual (venv)."""

    return [sys.executable, *args]
