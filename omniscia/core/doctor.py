"""Diagnostico de ambiente (doctor).

Objetivo:
- Reduzir "erro surpresa" na hora de usar tools.
- Dar instruções acionáveis (o que instalar/configurar) sem o usuário ter que caçar logs.

Este comando é offline e não usa LLM.
"""

from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass

from omniscia.core.config import Settings


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    fix: str | None = None


def _can_import(module: str) -> tuple[bool, str]:
    try:
        importlib.import_module(module)
        return True, "ok"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def run_doctor(*, settings: Settings | None = None) -> tuple[bool, str]:
    settings = settings or Settings.load()

    checks: list[Check] = []

    in_venv = sys.prefix != sys.base_prefix
    checks.append(
        Check(
            name="Python",
            ok=True,
            detail=f"{sys.version.split()[0]} ({sys.executable})",
        )
    )
    checks.append(
        Check(
            name="Virtualenv",
            ok=in_venv,
            detail="ativo" if in_venv else "não detectado",
            fix="Ative a .venv antes de rodar (Windows): .venv\\Scripts\\activate",
        )
    )

    checks.append(
        Check(
            name="CWD",
            ok=True,
            detail=os.getcwd(),
        )
    )

    # Core deps (devem existir sempre)
    for mod in ["typer", "rich", "pydantic", "dotenv", "httpx", "litellm"]:
        ok, detail = _can_import(mod)
        checks.append(
            Check(
                name=f"import {mod}",
                ok=ok,
                detail=detail,
                fix=None if ok else "Instale dependências base: pip install -r requirements.txt",
            )
        )

    # Opcionais agrupados por extra
    optional_groups: list[tuple[str, list[str], str]] = [
        ("os", ["pyautogui"], "pip install -e .[all]  # ou .[os]"),
        ("web", ["playwright"], "pip install -e .[all]  # ou .[web]"),
        ("vision", ["mss", "PIL", "pytesseract"], "pip install -e .[all]  # ou .[vision]"),
        ("voice", ["pyttsx3", "sounddevice", "soundfile", "vosk"], "pip install -e .[all]  # ou .[voice]"),
        (
            "memory",
            ["chromadb", "sentence_transformers", "cryptography", "keyring"],
            "pip install -e .[all]  # ou .[memory]",
        ),
    ]

    for extra, modules, fix in optional_groups:
        any_missing = False
        details: list[str] = []
        for mod in modules:
            ok, detail = _can_import(mod)
            if not ok:
                any_missing = True
            details.append(f"{mod}: {'ok' if ok else detail}")
        checks.append(
            Check(
                name=f"Extras [{extra}]",
                ok=(not any_missing),
                detail="; ".join(details),
                fix=None if not any_missing else fix,
            )
        )

    # Playwright needs browser binaries in addition to the Python package.
    pw_ok, _ = _can_import("playwright")
    if pw_ok:
        browsers_ok = False
        detail = "nao encontrado"

        # Try to detect browser caches in common locations.
        candidates: list[str] = []
        # Windows
        localapp = os.getenv("LOCALAPPDATA")
        if localapp:
            candidates.append(os.path.join(localapp, "ms-playwright"))
        # Linux/macOS (default cache)
        home = os.path.expanduser("~")
        if home:
            candidates.append(os.path.join(home, ".cache", "ms-playwright"))
            candidates.append(os.path.join(home, "Library", "Caches", "ms-playwright"))

        for base in candidates:
            try:
                if base and os.path.isdir(base):
                    # Heuristic: any subdir present indicates installs.
                    sub = [n for n in os.listdir(base) if os.path.isdir(os.path.join(base, n))]
                    if sub:
                        browsers_ok = True
                        detail = base
                        break
            except Exception:
                continue

        checks.append(
            Check(
                name="Playwright browsers",
                ok=browsers_ok,
                detail=detail,
                fix=None if browsers_ok else "Depois de instalar: python -m playwright install",
            )
        )

    # Settings sanity
    checks.append(
        Check(
            name="Router",
            ok=True,
            detail=f"mode={settings.router_mode}",
        )
    )

    # LLM sanity: common source of "error toda hora" when router_mode=llm.
    if str(settings.router_mode).lower() == "llm":
        provider_ok = bool(getattr(settings, "llm_provider", None))
        api_key_ok = bool(getattr(settings, "llm_api_key", None))
        model_ok = bool(getattr(settings, "llm_model", None))

        checks.append(
            Check(
                name="LLM provider",
                ok=provider_ok,
                detail=str(getattr(settings, "llm_provider", "") or "(vazio)"),
                fix="Configure OMNI_LLM_PROVIDER no .env ou troque OMNI_ROUTER_MODE=heuristic",
            )
        )
        checks.append(
            Check(
                name="LLM api key",
                ok=api_key_ok,
                detail="set" if api_key_ok else "(vazio)",
                fix="Configure OMNI_LLM_API_KEY no .env ou troque OMNI_ROUTER_MODE=heuristic",
            )
        )
        checks.append(
            Check(
                name="LLM model",
                ok=model_ok,
                detail=str(getattr(settings, "llm_model", "") or "(vazio)"),
                fix="Configure OMNI_LLM_MODEL no .env (ou use o padrao do provider)",
            )
        )

    if settings.tesseract_cmd:
        checks.append(
            Check(
                name="Tesseract",
                ok=True,
                detail=f"tesseract_cmd={settings.tesseract_cmd}",
            )
        )
    else:
        checks.append(
            Check(
                name="Tesseract",
                ok=False,
                detail="tesseract_cmd não configurado",
                fix="Se for usar OCR: instale o Tesseract e configure OMNI_TESSERACT_CMD no .env",
            )
        )

    ok_all = all(c.ok for c in checks)

    lines: list[str] = []
    # Use ASCII-only output to avoid encoding issues in some Windows terminals.
    lines.append("== Doctor (diagnostico) ==")
    for c in checks:
        status = "OK" if c.ok else "FAIL"
        lines.append(f"[{status}] {c.name}: {c.detail}")
        if (not c.ok) and c.fix:
            lines.append(f"       -> {c.fix}")

    if ok_all:
        lines.append("\nResumo: ambiente parece OK.")
    else:
        lines.append("\nResumo: ha pendencias. Resolva os itens FAIL acima para reduzir erros.")

    return ok_all, "\n".join(lines)
