"""Auto-correção baseada em comando (MVP).

Objetivo:
- Rodar um comando allowlisted (ex: pytest)
- Se falhar, capturar stdout/stderr
- Extrair uma lista pequena de arquivos citados no traceback/log
- Pedir ao LLM edições em JSON e aplicar
- Repetir por até N iterações

Formato de resposta do LLM (APENAS JSON):
{
  "edits": [
    {"path": "relative/path.py", "content": "..."}
  ],
  "note": "opcional"
}

Guardrails:
- Paths relativos, sem '..' e sem drive.
- Máximo de arquivos editados por iteração.
- Tamanho máximo de conteúdo por arquivo.
- Sem LLM configurado: não altera nada.

Este é um MVP intencionalmente simples.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from omniscia.core.config import Settings
from omniscia.core.litellm_env import provider_requires_api_key
from omniscia.modules.dev_agent.sandbox import parse_command, run_command

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AutoFixCmdResult:
    status: str  # ok | failed | needs_llm
    iters: int
    summary: str
    last_exit_code: int | None = None


def _safe_rel_path(path: str) -> Path:
    p = (path or "").strip().replace("\\", "/")
    if not p:
        raise ValueError("path vazio")
    if p.startswith("/") or ":" in p:
        raise ValueError("path deve ser relativo")
    if ".." in p.split("/"):
        raise ValueError("path não pode conter '..'")
    return Path(p)


def _extract_file_paths(text: str) -> list[str]:
    """Extrai paths prováveis de arquivos Python de logs/tracebacks.

    Heurísticas:
- traceback padrão: File "...", line N, in ...
- também tenta capturar algo que pareça *.py

    Retorna paths normalizados com '/'.
    """

    if not text:
        return []

    paths: list[str] = []

    for m in re.finditer(r"File \"([^\"]+?\.py)\"", text):
        paths.append(m.group(1))

    for m in re.finditer(r"\b([\w\-./\\]+\.py)\b", text):
        paths.append(m.group(1))

    # Normaliza + dedup preservando ordem.
    seen: set[str] = set()
    out: list[str] = []
    for p in paths:
        p2 = p.strip().replace("\\", "/")
        # Ignora paths absolutos.
        if not p2 or p2.startswith("/") or ":" in p2:
            continue
        if ".." in p2.split("/"):
            continue
        if p2 not in seen:
            seen.add(p2)
            out.append(p2)
    return out


def autofix_command(
    *,
    settings: Settings,
    command: str,
    max_iters: int = 3,
    timeout_s: float = 120.0,
    max_files: int = 4,
    max_file_chars: int = 18000,
) -> AutoFixCmdResult:
    """Executa um comando e tenta corrigir falhas via LLM."""

    argv = parse_command(command)
    if not argv:
        return AutoFixCmdResult(status="failed", iters=0, summary="comando vazio")

    # Guardrail MVP: este loop é para testes. Permitimos apenas pytest.
    exe = argv[0].lower().replace("\\", "/")
    is_pytest = exe.endswith("pytest") or exe.endswith("pytest.exe") or exe == "pytest"
    is_python_pytest = (
        exe.endswith("python")
        or exe.endswith("python.exe")
        or exe == "python"
    ) and len(argv) >= 3 and argv[1] == "-m" and argv[2] == "pytest"

    if not (is_pytest or is_python_pytest):
        return AutoFixCmdResult(
            status="failed",
            iters=0,
            summary="autofix_cmd só permite pytest (use dev.exec com HITL para outros comandos)",
        )

    needs_key = provider_requires_api_key(settings.llm_provider)
    has_key = bool((settings.llm_api_key or "").strip())
    if not (settings.llm_provider and settings.llm_model and (has_key or not needs_key)):
        return AutoFixCmdResult(
            status="needs_llm",
            iters=0,
            summary="LLM não configurado (defina OMNI_LLM_PROVIDER/OMNI_LLM_MODEL/OMNI_LLM_API_KEY)",
        )

    for i in range(1, max_iters + 1):
        try:
            res = run_command(argv=argv, cwd=Path("."), timeout_s=timeout_s)
        except Exception as e:  # noqa: BLE001
            return AutoFixCmdResult(status="failed", iters=i, summary=f"falha ao executar: {e}")

        if res.exit_code == 0:
            return AutoFixCmdResult(status="ok", iters=i, summary="comando executou sem erros", last_exit_code=0)

        evidence = _build_evidence(res.stdout, res.stderr)
        file_paths = _extract_file_paths(evidence)[:max_files]
        file_blobs = _read_files(file_paths, max_chars=max_file_chars)

        edits = _ask_llm_for_edits(
            settings=settings,
            command=command,
            stdout=res.stdout,
            stderr=res.stderr,
            files=file_blobs,
        )

        if not edits:
            return AutoFixCmdResult(
                status="failed",
                iters=i,
                summary="LLM não retornou edições aplicáveis",
                last_exit_code=res.exit_code,
            )

        applied = 0
        for edit in edits[:max_files]:
            try:
                target = _safe_rel_path(str(edit.get("path", "")))
                content = str(edit.get("content", ""))
                if not content.strip():
                    continue
                if len(content) > max_file_chars:
                    content = content[:max_file_chars] + "\n# ... [truncado]"

                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                applied += 1
            except Exception:
                logger.exception("Falha aplicando edit")

        if applied == 0:
            return AutoFixCmdResult(
                status="failed",
                iters=i,
                summary="não consegui aplicar nenhuma edição",
                last_exit_code=res.exit_code,
            )

    return AutoFixCmdResult(status="failed", iters=max_iters, summary="atingiu limite de iterações")


def _build_evidence(stdout: str, stderr: str) -> str:
    parts = []
    if stdout:
        parts.append("=== STDOUT ===\n" + stdout)
    if stderr:
        parts.append("=== STDERR ===\n" + stderr)
    return "\n\n".join(parts)


def _read_files(paths: Iterable[str], *, max_chars: int) -> list[dict[str, str]]:
    blobs: list[dict[str, str]] = []
    for p in paths:
        try:
            rel = _safe_rel_path(p)
            if not rel.exists() or not rel.is_file():
                continue
            content = rel.read_text(encoding="utf-8", errors="replace")
            if len(content) > max_chars:
                content = content[:max_chars] + "\n... [truncado]"
            blobs.append({"path": str(rel).replace("\\", "/"), "content": content})
        except Exception:
            logger.exception("Falha lendo arquivo para contexto")
    return blobs


def _ask_llm_for_edits(
    *,
    settings: Settings,
    command: str,
    stdout: str,
    stderr: str,
    files: list[dict[str, str]],
) -> list[dict[str, Any]] | None:
    try:
        from litellm import completion
    except Exception:
        logger.exception("litellm indisponível")
        return None

    needs_key = provider_requires_api_key(settings.llm_provider)
    has_key = bool((settings.llm_api_key or "").strip())
    if not (settings.llm_provider and settings.llm_model and (has_key or not needs_key)):
        return None

    system = (
        "Você é um agente de correção de bugs. "
        "Seu objetivo é fazer o comando passar com a MENOR mudança possível. "
        "Responda APENAS JSON válido no formato: "
        "{\"edits\":[{\"path\":string,\"content\":string}],\"note\":string}. "
        "Sem markdown. Sem texto extra. "
        "Regras: use apenas paths relativos existentes no projeto; não use '..' nem paths absolutos. "
        "Edite no máximo 4 arquivos." 
    )

    payload = {
        "command": command,
        "stdout": stdout,
        "stderr": stderr,
        "files": files,
    }

    from omniscia.core.litellm_env import apply_litellm_env

    apply_litellm_env(settings)

    try:
        resp = completion(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.0,
        )

        content: str = resp["choices"][0]["message"]["content"]  # type: ignore[index]
        raw = content.strip()
        try:
            data: dict[str, Any] = json.loads(raw)
        except Exception:
            start = raw.find("{")
            end = raw.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise
            data = json.loads(raw[start : end + 1])

        edits = data.get("edits")
        if not isinstance(edits, list) or not edits:
            return None
        # Sanitiza estrutura mínima.
        out: list[dict[str, Any]] = []
        for e in edits:
            if not isinstance(e, dict):
                continue
            if not str(e.get("path", "")).strip():
                continue
            out.append({"path": str(e["path"]), "content": str(e.get("content", ""))})
        return out or None
    except Exception as e:
        from omniscia.core.redact import redact_secrets

        logger.error("Falha ao obter edits do LLM (%s)", redact_secrets(str(e)))
        return None
