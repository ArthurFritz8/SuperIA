"""Auto-correção (MVP) para arquivos Python.

O objetivo aqui é fechar um ciclo básico:
- Rodar um arquivo Python
- Se falhar, capturar stdout/stderr
- Pedir ao LLM uma versão corrigida do arquivo (formato JSON estrito)
- Aplicar a correção e repetir

Segurança (MVP):
- Só opera em paths relativos (sem drive, sem '..').
- Só modifica o arquivo alvo.
- Só executa Python via `sys.executable` (sandbox allowlisted).
- Se não houver LLM configurado, NÃO tenta "inventar" correções.

Nota:
- Isto é o núcleo do "Programador Interno". Evolui depois para múltiplos arquivos,
  patches parciais, execução de testes e mudanças estruturais.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from omniscia.core.config import Settings
from omniscia.core.litellm_env import provider_requires_api_key
from omniscia.modules.dev_agent.sandbox import python_argv, run_command

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AutoFixResult:
    status: str  # ok | failed | needs_llm
    iters: int
    summary: str


def _safe_rel_path(path: str) -> Path:
    p = (path or "").strip().replace("\\", "/")
    if not p:
        raise ValueError("path vazio")
    if p.startswith("/") or ":" in p:
        raise ValueError("path deve ser relativo")
    if ".." in p.split("/"):
        raise ValueError("path não pode conter '..'")
    return Path(p)


def autofix_python_file(
    *,
    settings: Settings,
    path: str,
    max_iters: int = 3,
    timeout_s: float = 60.0,
) -> AutoFixResult:
    """Tenta corrigir um arquivo Python até passar.

    Dependências:
- Requer LLM configurado (OMNI_LLM_PROVIDER/MODEL/API_KEY).
    """

    target = _safe_rel_path(path)
    if not target.exists() or not target.is_file():
        return AutoFixResult(status="failed", iters=0, summary="arquivo não existe")

    needs_key = provider_requires_api_key(settings.llm_provider)
    has_key = bool((settings.llm_api_key or "").strip())
    if not (settings.llm_provider and settings.llm_model and (has_key or not needs_key)):
        return AutoFixResult(
            status="needs_llm",
            iters=0,
            summary="LLM não configurado (defina OMNI_LLM_PROVIDER/OMNI_LLM_MODEL/OMNI_LLM_API_KEY)",
        )

    for i in range(1, max_iters + 1):
        run = run_command(argv=python_argv(str(target)), cwd=Path("."), timeout_s=timeout_s)
        if run.exit_code == 0:
            return AutoFixResult(status="ok", iters=i, summary="arquivo executou sem erros")

        # Preparar prompt de correção.
        original = target.read_text(encoding="utf-8", errors="replace")
        fix = _ask_llm_for_fixed_file(
            settings=settings,
            file_path=str(target),
            original_code=original,
            stdout=run.stdout,
            stderr=run.stderr,
        )

        if fix is None:
            return AutoFixResult(status="failed", iters=i, summary="LLM falhou ao gerar correção")

        # Só aplica se mudou algo.
        if fix.strip() == original.strip():
            return AutoFixResult(status="failed", iters=i, summary="LLM retornou código idêntico")

        target.write_text(fix, encoding="utf-8")

    return AutoFixResult(status="failed", iters=max_iters, summary="atingiu limite de iterações")


def _ask_llm_for_fixed_file(
    *,
    settings: Settings,
    file_path: str,
    original_code: str,
    stdout: str,
    stderr: str,
) -> str | None:
    """Pede ao LLM uma versão corrigida do arquivo.

    Protocolo:
- O LLM deve retornar APENAS JSON: {"fixed_code": "..."}
- Sem markdown, sem explicações.

    Segurança:
- Não inclui segredos no prompt.
- O arquivo corrigido é aplicado somente ao path alvo.
    """

    try:
        from litellm import completion
    except Exception:
        logger.exception("litellm indisponível")
        return None

    system = (
        "Você é um assistente de correção de bugs em Python. "
        "Receba um arquivo e um erro, e devolva APENAS JSON válido no formato: "
        "{\"fixed_code\": string}. "
        "Não inclua markdown. Não inclua explicações. "
        "Mantenha a intenção original do código e faça a menor mudança possível para corrigir o erro."
    )

    user = (
        f"Arquivo: {file_path}\n\n"
        "=== CÓDIGO ORIGINAL ===\n"
        f"{original_code}\n\n"
        "=== STDOUT ===\n"
        f"{stdout}\n\n"
        "=== STDERR ===\n"
        f"{stderr}\n"
    )

    needs_key = provider_requires_api_key(settings.llm_provider)
    has_key = bool((settings.llm_api_key or "").strip())
    if not (settings.llm_provider and settings.llm_model and (has_key or not needs_key)):
        return None

    llm_model: str = settings.llm_model

    from omniscia.core.litellm_env import apply_litellm_env

    apply_litellm_env(settings)

    try:
        resp = completion(
            model=llm_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.0,
        )

        content: str = resp["choices"][0]["message"]["content"]  # type: ignore[index]
        data: dict[str, Any] = json.loads(content)
        fixed = str(data.get("fixed_code", ""))
        if not fixed.strip():
            return None
        return fixed
    except Exception as e:
        from omniscia.core.redact import redact_secrets

        logger.error("Falha ao obter correção do LLM (%s)", redact_secrets(str(e)))
        return None
