"""Registro de ferramentas web (Playwright).

Rationale:
- Mantemos as ferramentas fora do core para isolar dependências pesadas.
- O core chama `register_web_tools()` e essas tools só funcionam se Playwright estiver instalado.

Segurança:
- As tools aqui são *read-only* por design (não fazem login, não compram, não postam).
- Mesmo assim, elas podem gerar arquivos (screenshots) em path relativo e controlado.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from omniscia.core.config import Settings
from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult


def register_web_tools(registry: ToolRegistry, settings: Settings) -> None:
    registry.register(
        ToolSpec(
            name="web.get_page_text",
            description="Abre uma URL e retorna texto do body (read-only)",
            risk="MEDIUM",
            fn=lambda args: _web_get_page_text(args, settings=settings),
        )
    )

    registry.register(
        ToolSpec(
            name="web.screenshot",
            description="Tira screenshot de uma URL e salva como PNG (path relativo)",
            risk="MEDIUM",
            fn=lambda args: _web_screenshot(args, settings=settings),
        )
    )


def _require_playwright() -> tuple[bool, str | None]:
    try:
        import playwright  # noqa: F401

        return True, None
    except Exception:
        return (
            False,
            "Playwright não está instalado. Instale com: pip install playwright && playwright install",
        )


def _web_get_page_text(args: dict[str, Any], *, settings: Settings) -> ToolResult:
    ok, err = _require_playwright()
    if not ok:
        return ToolResult(status="error", error=err)

    url = str(args.get("url", "")).strip()
    max_chars = int(args.get("max_chars", 6000) or 6000)

    if not (url.startswith("http://") or url.startswith("https://")):
        return ToolResult(status="error", error="url inválida (use http/https)")

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=settings.web_headless)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)

            # `inner_text('body')` tende a ser mais útil do que HTML cru para RAG.
            text = page.inner_text("body")
            browser.close()

        text = (text or "").strip()
        if len(text) > max_chars:
            text = text[:max_chars] + "\n... [truncado]"

        return ToolResult(status="ok", output=text)
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _web_screenshot(args: dict[str, Any], *, settings: Settings) -> ToolResult:
    ok, err = _require_playwright()
    if not ok:
        return ToolResult(status="error", error=err)

    url = str(args.get("url", "")).strip()
    path = str(args.get("path", "data/screenshots/page.png")).strip().replace("\\", "/")
    full_page = bool(args.get("full_page", True))

    if not (url.startswith("http://") or url.startswith("https://")):
        return ToolResult(status="error", error="url inválida (use http/https)")

    # Guardrail: apenas paths relativos e apenas PNG.
    if not path or path.startswith("/") or ":" in path:
        return ToolResult(status="error", error="path inválido (use path relativo)")
    if not path.lower().endswith(".png"):
        return ToolResult(status="error", error="path deve terminar com .png")

    try:
        from playwright.sync_api import sync_playwright

        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=settings.web_headless)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            page.screenshot(path=str(out), full_page=full_page)
            browser.close()

        return ToolResult(status="ok", output=f"saved screenshot: {path}")
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))
