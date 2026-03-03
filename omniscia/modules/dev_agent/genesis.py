"""Gênese: ciclo fechado de auto-programação para aprender tools.

Fluxo (MVP):
- Gera um módulo de tool (código) via LLM.
- Escreve em scratch/temp_tool_<name>.py.
- Executa um self-test (o próprio arquivo) e usa autofix (LLM) se falhar.
- Se passar, copia para omniscia/tools/custom/<name>.py e faz hot-reload.

Guardrails:
- Exige Settings.self_coding_enabled e Settings.custom_tools_enabled.
- Só escreve em scratch/ e omniscia/tools/custom.
- Limita iterações.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from omniscia.core.config import Settings
from omniscia.core.litellm_env import apply_litellm_env
from omniscia.core.litellm_env import provider_requires_api_key
from omniscia.core.tools import ToolRegistry
from omniscia.core.redact import redact_secrets
from omniscia.modules.dev_agent.autofix import autofix_python_file


def _safe_module_name(name: str) -> str:
    """Sanitiza nome de módulo Python (mesma regra do DevAgent).

    Permitimos: letras, números, underscore. Começa com letra/underscore.
    Substitui '.' e '-' por '_' para permitir nomes estilo tool (ex: crypto.quote).
    """

    n = (name or "").strip().replace("-", "_").replace(".", "_")
    out: list[str] = []
    for ch in n:
        if ch.isalnum() or ch == "_":
            out.append(ch)
    s = "".join(out)
    if not s:
        raise ValueError("name inválido")
    if not (s[0].isalpha() or s[0] == "_"):
        s = "_" + s
    return s[:64]

logger = logging.getLogger(__name__)


def _llm_can_run(settings: Settings) -> tuple[bool, str | None]:
    needs_key = provider_requires_api_key(settings.llm_provider)
    has_key = bool((settings.llm_api_key or "").strip())
    if not (settings.llm_provider and settings.llm_model and (has_key or not needs_key)):
        return False, "LLM não configurado (OMNI_LLM_PROVIDER/OMNI_LLM_MODEL/OMNI_LLM_API_KEY)"
    return True, None


def _render_tool_prompt(*, tool_name: str, description: str) -> tuple[str, str]:
    system = (
        "Você é um engenheiro Python sênior. Gere um módulo Python para uma tool do Omniscia. "
        "Regras obrigatórias:\n"
        "- O módulo deve definir register(registry) e registrar exatamente 1 ToolSpec.\n"
        "- O ToolSpec.name deve ser: 'custom." + tool_name + "'\n"
        "- A tool deve ser guardrailed (paths relativos quando houver IO).\n"
        "- O módulo DEVE ser executável como script e fazer um self-test no __main__ (sem rede).\n"
        "- Retorne APENAS JSON válido: {\"code\": \"...\"}. Sem markdown.\n"
    )

    user = (
        f"Crie a tool custom.{tool_name}.\n\n"
        f"Descrição funcional:\n{description.strip()}\n\n"
        "Contexto do projeto:\n"
        "- Existe ToolRegistry e ToolSpec em omniscia.core.tools\n"
        "- ToolResult em omniscia.core.types\n"
        "- Tools rodam síncronas e recebem args: dict\n"
    )

    return system, user


def _ask_llm_for_tool_code(*, settings: Settings, tool_name: str, description: str) -> tuple[str | None, str | None]:
    ok, err = _llm_can_run(settings)
    if not ok:
        return None, err

    try:
        from litellm import completion
    except Exception:
        logger.exception("litellm indisponível")
        return None, "litellm indisponível"

    system, user = _render_tool_prompt(tool_name=tool_name, description=description)
    apply_litellm_env(settings)

    try:
        resp = completion(
            model=str(settings.llm_model),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.0,
        )
        content: str = resp["choices"][0]["message"]["content"]  # type: ignore[index]
        data: dict[str, Any] = json.loads(content)
        code = str(data.get("code", "") or "")
        if not code.strip():
            return None, "LLM retornou JSON sem campo 'code'"
        return code, None
    except Exception as exc:  # noqa: BLE001
        logger.error("Falha gerando tool via LLM: %s", redact_secrets(str(exc)))
        return None, "falha chamando LLM"


def genesis_create_tool_closed_loop(
    *,
    registry: ToolRegistry,
    settings: Settings,
    name: str,
    description: str,
    max_iters: int = 3,
) -> tuple[bool, str]:
    if not bool(getattr(settings, "self_coding_enabled", False)):
        return False, "self-coding desabilitado (OMNI_SELF_CODING_ENABLED=false)"
    if not bool(getattr(settings, "custom_tools_enabled", False)):
        return False, "custom tools desabilitadas (OMNI_CUSTOM_TOOLS_ENABLED=false)"

    raw_name = str(name or "").strip()
    if not raw_name:
        return False, "informe name"
    if not str(description or "").strip():
        return False, "informe description"

    try:
        mod = _safe_module_name(raw_name)
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)

    code, gen_err = _ask_llm_for_tool_code(settings=settings, tool_name=mod, description=description)
    if code is None:
        return False, gen_err or "LLM não conseguiu gerar o código da tool"

    scratch_dir = Path("scratch")
    scratch_dir.mkdir(parents=True, exist_ok=True)
    scratch_path = scratch_dir / f"temp_tool_{mod}.py"
    scratch_path.write_text(code, encoding="utf-8")

    # Auto-fix rodando o próprio arquivo (self-test no __main__).
    fix = autofix_python_file(settings=settings, path=scratch_path.as_posix(), max_iters=max_iters, timeout_s=60.0)
    if fix.status != "ok":
        return False, f"self-test não passou: {fix.summary}"

    final_code = scratch_path.read_text(encoding="utf-8", errors="replace")

    out_dir = Path("omniscia/tools/custom")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{mod}.py"
    out_path.write_text(final_code, encoding="utf-8")

    # Hot-reload.
    try:
        from omniscia.tools.custom.loader import load_custom_tools

        load_custom_tools(registry)
    except Exception as exc:  # noqa: BLE001
        return False, f"tool criada, mas hot-reload falhou: {exc}"

    return True, f"aprendi a tool custom.{mod} (módulo: {out_path.as_posix()})"
