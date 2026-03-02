"""Project scaffolding (safe, workspace-only).

Goal:
- Turn "crie um projeto" into a real action without requiring external CLIs.
- Keep guardrails: only writes inside workspace, no traversal, no overwrites by default.

This is intentionally small but creates a solid starting point.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from omniscia.core.types import ToolResult


def _safe_rel_path(raw: str) -> Path:
    s = (raw or "").strip().strip('"').strip("'").replace("\\", "/")
    if not s:
        raise ValueError("path vazio")
    if s.startswith("/") or ":" in s:
        raise ValueError("path deve ser relativo")
    if any(part == ".." for part in Path(s).parts):
        raise ValueError("path não pode conter '..'")
    return Path(s)


def _slugify_name(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return "meu_projeto"
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9_\- ]+", "", s)
    s = re.sub(r"\s+", "_", s)
    s = s.strip("_-")
    return s or "meu_projeto"


def scaffold_python_project(args: dict[str, Any]) -> ToolResult:
    """Create a minimal Python project (src layout + pytest).

    Args:
    - name: project name (required-ish)
    - path: relative folder to create under workspace (optional)
    - overwrite: bool (default False)
    """

    name_raw = str(args.get("name", "") or "").strip()
    project_name = _slugify_name(name_raw)
    overwrite = bool(args.get("overwrite", False))

    raw_path = str(args.get("path", "") or "").strip()
    if raw_path:
        base = _safe_rel_path(raw_path)
    else:
        base = Path("scratch/projects") / project_name

    root = base
    if root.exists() and not overwrite:
        return ToolResult(status="error", error=f"destino já existe: {root}")

    pkg = project_name.replace("-", "_")
    src_pkg = root / "src" / pkg
    tests_dir = root / "tests"

    try:
        src_pkg.mkdir(parents=True, exist_ok=True)
        tests_dir.mkdir(parents=True, exist_ok=True)

        (root / "README.md").write_text(
            f"# {project_name}\n\nProjeto criado pelo SuperIA (scaffold).\n",
            encoding="utf-8",
        )

        (root / ".gitignore").write_text(
            "__pycache__/\n.pytest_cache/\n.venv/\ndist/\nbuild/\n*.egg-info/\n",
            encoding="utf-8",
        )

        (src_pkg / "__init__.py").write_text("__all__ = []\n", encoding="utf-8")

        (src_pkg / "__main__.py").write_text(
            "def main() -> None:\n"
            "    print(\"Olá! Projeto pronto.\")\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n",
            encoding="utf-8",
        )

        (tests_dir / "test_smoke.py").write_text(
            f"def test_import():\n    import {pkg}  # noqa: F401\n",
            encoding="utf-8",
        )

        (root / "pyproject.toml").write_text(
            "[build-system]\n"
            "requires = ['setuptools>=68']\n"
            "build-backend = 'setuptools.build_meta'\n\n"
            "[project]\n"
            f"name = '{project_name}'\n"
            "version = '0.1.0'\n"
            "requires-python = '>=3.10'\n"
            "dependencies = []\n\n"
            "[tool.pytest.ini_options]\n"
            "pythonpath = ['src']\n"
            "addopts = '-q'\n",
            encoding="utf-8",
        )

        next_steps = (
            f"created project at {root}\n"
            "next:\n"
            f"- cd {root}\n"
            "- python -m venv .venv\n"
            "- .venv/Scripts/python -m pip install -U pip pytest\n"
            f"- .venv/Scripts/python -m {pkg}\n"
            "- .venv/Scripts/python -m pytest\n"
        )

        return ToolResult(status="ok", output=next_steps)
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))
