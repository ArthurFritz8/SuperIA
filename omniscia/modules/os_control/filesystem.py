"""Ferramentas de filesystem (guardrailed).

Rationale:
- Um agente que manipula arquivos precisa de guardrails fortes.

Guardrails principais:
- Apenas paths relativos (sem drive letter, sem "/", sem ".." escapando)
- Operações destrutivas (delete) devem ser marcadas como CRITICAL no plano (HITL)

Nota:
- Neste MVP, o "workspace root" é o diretório atual do processo.
  Depois podemos fixar explicitamente via Settings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult


def register_filesystem_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="fs.list_dir",
            description="Lista arquivos/pastas em um path relativo",
            risk="LOW",
            fn=_fs_list_dir,
        )
    )
    registry.register(
        ToolSpec(
            name="fs.read_text",
            description="Lê arquivo texto (utf-8) em path relativo",
            risk="MEDIUM",
            fn=_fs_read_text,
        )
    )
    registry.register(
        ToolSpec(
            name="fs.delete",
            description="Apaga arquivo/pasta (recursivo) em path relativo (CRITICAL)",
            risk="CRITICAL",
            fn=_fs_delete,
        )
    )


def _safe_rel_path(raw: str) -> Path:
    path = (raw or "").strip().replace("\\", "/")
    if not path:
        raise ValueError("path vazio")
    if path.startswith("/") or ":" in path:
        raise ValueError("path deve ser relativo")

    p = Path(path)

    # Evita path traversal fora do workspace.
    if any(part == ".." for part in p.parts):
        raise ValueError("path não pode conter '..'")

    return p


def _fs_list_dir(args: dict[str, Any]) -> ToolResult:
    try:
        p = _safe_rel_path(str(args.get("path", ".")))
        if not p.exists():
            return ToolResult(status="error", error="path não existe")
        if not p.is_dir():
            return ToolResult(status="error", error="path não é diretório")

        items = []
        for child in sorted(p.iterdir(), key=lambda x: x.name.lower()):
            suffix = "/" if child.is_dir() else ""
            items.append(child.name + suffix)

        return ToolResult(status="ok", output="\n".join(items) if items else "(vazio)")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _fs_read_text(args: dict[str, Any]) -> ToolResult:
    try:
        p = _safe_rel_path(str(args.get("path", "")))
        max_chars = int(args.get("max_chars", 8000) or 8000)
        if not p.exists() or not p.is_file():
            return ToolResult(status="error", error="arquivo não existe")

        text = p.read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars:
            text = text[:max_chars] + "\n... [truncado]"

        return ToolResult(status="ok", output=text)
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _fs_delete(args: dict[str, Any]) -> ToolResult:
    """Apaga arquivo ou pasta.

    Importante:
    - O HITL acontece antes da execução (no core), mas mantemos guardrails aqui também.
    - Não permitimos deletar '.' (workspace) por padrão.
    """

    try:
        p = _safe_rel_path(str(args.get("path", "")))
        if str(p) in {".", "./"}:
            return ToolResult(status="error", error="não é permitido apagar o workspace (.)")

        if not p.exists():
            return ToolResult(status="ok", output="(nada para apagar)")

        if p.is_dir():
            for child in sorted(p.rglob("*"), reverse=True):
                if child.is_file() or child.is_symlink():
                    child.unlink(missing_ok=True)
                elif child.is_dir():
                    child.rmdir()
            p.rmdir()
        else:
            p.unlink(missing_ok=True)

        return ToolResult(status="ok", output=f"deleted {p}")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))
