"""Self-test offline do Omnisciência.

Objetivo:
- Validar que o core importa, configura e executa ferramentas básicas.
- Não usar LLM nem depender de módulos opcionais (Playwright/Tesseract/PyAutoGUI).

O selftest é intencionalmente rápido e determinístico.
"""

from __future__ import annotations

from dataclasses import dataclass

from omniscia.core.config import Settings
from omniscia.core.router import route
from omniscia.core.tools import build_default_registry


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


def run_selftest() -> tuple[bool, str]:
    checks: list[CheckResult] = []

    # Settings load (não deve falhar mesmo sem .env)
    try:
        settings = Settings.load()
        checks.append(CheckResult("settings.load", True, f"router_mode={settings.router_mode}"))
    except Exception as exc:  # noqa: BLE001
        checks.append(CheckResult("settings.load", False, str(exc)))
        return False, _format_report(checks)

    # Registry build
    try:
        registry = build_default_registry(settings=settings, memory_store=None)
        tool_names = {t.name for t in registry.list()}
        required = {"core.list_tools", "core.show_settings", "fs.list_dir", "fs.read_text"}
        missing = sorted(required - tool_names)
        if missing:
            checks.append(CheckResult("registry", False, f"missing tools: {missing}"))
        else:
            checks.append(CheckResult("registry", True, f"tools={len(tool_names)}"))
    except Exception as exc:  # noqa: BLE001
        checks.append(CheckResult("registry", False, str(exc)))
        return False, _format_report(checks)

    # Deterministic routing for filesystem (should not require LLM)
    try:
        s2 = Settings(
            **{
                **settings.__dict__,
                "router_mode": "llm",
                "llm_provider": "groq",
                "llm_model": "groq/llama-3.3-70b-versatile",
                "llm_api_key": "test-key",
            }
        )
        plan = route(s2, "copiar data/tmp/a.txt para data/tmp/b.txt")
        checks.append(CheckResult("route.fs.copy", plan.intent == "fs.copy", f"intent={plan.intent}"))
    except Exception as exc:  # noqa: BLE001
        checks.append(CheckResult("route.fs.copy", False, str(exc)))

    # Basic FS tools (write_file + fs.copy + fs.move)
    try:
        registry.run("fs.mkdir", {"path": "data/tmp/selftest"})
        w = registry.run("write_file", {"path": "data/tmp/selftest/a.txt", "content": "ok"})
        c = registry.run(
            "fs.copy",
            {"src": "data/tmp/selftest/a.txt", "dst": "data/tmp/selftest/b.txt", "overwrite": True},
        )
        m = registry.run(
            "fs.move",
            {"src": "data/tmp/selftest/b.txt", "dst": "data/tmp/selftest/c.txt", "overwrite": True},
        )
        ok = (w.status == "ok") and (c.status == "ok") and (m.status == "ok")
        checks.append(CheckResult("fs.routines", ok, f"write={w.status} copy={c.status} move={m.status}"))
    except Exception as exc:  # noqa: BLE001
        checks.append(CheckResult("fs.routines", False, str(exc)))

    all_ok = all(c.ok for c in checks)
    return all_ok, _format_report(checks)


def _format_report(checks: list[CheckResult]) -> str:
    lines: list[str] = ["== selftest =="]
    for c in checks:
        status = "OK" if c.ok else "FAIL"
        if c.detail:
            lines.append(f"- {status} {c.name}: {c.detail}")
        else:
            lines.append(f"- {status} {c.name}")
    return "\n".join(lines)
