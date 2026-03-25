"""Registro de ferramentas web (Playwright).

Rationale:
- Mantemos as ferramentas fora do core para isolar dependências pesadas.
- O core chama `register_web_tools()` e essas tools só funcionam se Playwright estiver instalado.

Segurança:
- As tools aqui são *read-only* por design (não fazem login, não compram, não postam).
- Mesmo assim, elas podem gerar arquivos (screenshots) em path relativo e controlado.
"""

from __future__ import annotations

import hashlib
import time
import asyncio
from pathlib import Path
from typing import Any
import json

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
            async_fn=lambda args: _web_get_page_text_async(args, settings=settings),
        )
    )

    registry.register(
        ToolSpec(
            name="web.screenshot",
            description="Tira screenshot de uma URL e salva como PNG (path relativo)",
            risk="MEDIUM",
            fn=lambda args: _web_screenshot(args, settings=settings),
            async_fn=lambda args: _web_screenshot_async(args, settings=settings),
        )
    )

    registry.register(
        ToolSpec(
            name="web.get_links",
            description="Extrai links (href + texto) de uma URL (read-only)",
            risk="MEDIUM",
            fn=lambda args: _web_get_links(args, settings=settings),
            async_fn=lambda args: _web_get_links_async(args, settings=settings),
        )
    )

    registry.register(
        ToolSpec(
            name="web.research",
            description=(
                "Pesquisa na web e retorna um resumo com fontes. "
                "Args: query, max_results?, max_pages?, max_chars_per_page?, save_to_memory?, summarize?"
            ),
            risk="MEDIUM",
            fn=lambda args: _web_research(args, settings=settings),
            async_fn=lambda args: _web_research_async(args, settings=settings),
        )
    )


async def _web_get_page_text_async(args: dict[str, Any], *, settings: Settings) -> ToolResult:
    # Mantém comportamento: se Playwright não existir, retorna erro igual.
    ok, err = _require_playwright()
    if not ok:
        return ToolResult(status="error", error=err)

    url = str(args.get("url", "")).strip()
    max_chars = int(args.get("max_chars", 6000) or 6000)

    if not (url.startswith("http://") or url.startswith("https://")):
        return ToolResult(status="error", error="url inválida (use http/https)")

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=settings.web_headless)
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            text = await page.inner_text("body")
            await browser.close()

        text = (text or "").strip()
        if len(text) > max_chars:
            text = text[:max_chars] + "\n... [truncado]"
        return ToolResult(status="ok", output=text)
    except Exception:
        # Fallback robusto: usa versão sync em thread.
        return await asyncio.to_thread(_web_get_page_text, args, settings=settings)


async def _web_screenshot_async(args: dict[str, Any], *, settings: Settings) -> ToolResult:
    ok, err = _require_playwright()
    if not ok:
        return ToolResult(status="error", error=err)

    url = str(args.get("url", "")).strip()
    path = str(args.get("path", "data/screenshots/page.png")).strip().replace("\\", "/")
    full_page = bool(args.get("full_page", True))

    if not (url.startswith("http://") or url.startswith("https://")):
        return ToolResult(status="error", error="url inválida (use http/https)")

    if not path or path.startswith("/") or ":" in path:
        return ToolResult(status="error", error="path inválido (use path relativo)")
    if not path.lower().endswith(".png"):
        return ToolResult(status="error", error="path deve terminar com .png")

    try:
        from playwright.async_api import async_playwright

        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=settings.web_headless)
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await page.screenshot(path=str(out), full_page=full_page)
            await browser.close()

        return ToolResult(status="ok", output=f"saved screenshot: {path}")
    except Exception:
        return await asyncio.to_thread(_web_screenshot, args, settings=settings)


async def _web_get_links_async(args: dict[str, Any], *, settings: Settings) -> ToolResult:
    ok, err = _require_playwright()
    if not ok:
        return ToolResult(status="error", error=err)

    url = str(args.get("url", "")).strip()
    max_links = int(args.get("max_links", 50) or 50)

    if not (url.startswith("http://") or url.startswith("https://")):
        return ToolResult(status="error", error="url inválida (use http/https)")

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=settings.web_headless)
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)

            anchors = await page.query_selector_all("a[href]")
            links: list[dict[str, str]] = []
            seen: set[str] = set()
            for a in anchors:
                href = (await a.get_attribute("href") or "").strip()
                text = (await a.inner_text() or "").strip()
                if not href:
                    continue

                abs_href = await page.evaluate("(a) => a.href", a)
                abs_href = (abs_href or href or "").strip()
                if abs_href in seen:
                    continue
                seen.add(abs_href)
                links.append({"href": abs_href, "text": text})
                if len(links) >= max_links:
                    break

            await browser.close()

        return ToolResult(status="ok", output=json.dumps({"url": url, "links": links}, ensure_ascii=False))
    except Exception:
        return await asyncio.to_thread(_web_get_links, args, settings=settings)


async def _web_research_async(args: dict[str, Any], *, settings: Settings) -> ToolResult:
    ok, err = _require_playwright()
    if not ok:
        return ToolResult(status="error", error=err)
    return await asyncio.to_thread(_web_research, args, settings=settings)


def _require_playwright() -> tuple[bool, str | None]:
    try:
        import playwright  # noqa: F401

        return True, None
    except Exception:
        return (
            False,
            "Playwright não está instalado. Instale com: pip install playwright && playwright install",
        )


def _stable_id(prefix: str, payload: str) -> str:
    h = hashlib.sha256()
    h.update((prefix or "").encode("utf-8", errors="ignore"))
    h.update(b"\n")
    h.update((payload or "").encode("utf-8", errors="ignore"))
    return h.hexdigest()[:28]


def _web_research(args: dict[str, Any], *, settings: Settings) -> ToolResult:
    ok, err = _require_playwright()
    if not ok:
        return ToolResult(status="error", error=err)

    query = str(args.get("query", "") or args.get("q", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe query")

    try:
        max_results = int(args.get("max_results", 5) or 5)
    except Exception:
        max_results = 5
    if max_results < 1:
        max_results = 1
    if max_results > 10:
        max_results = 10

    try:
        max_pages = int(args.get("max_pages", 3) or 3)
    except Exception:
        max_pages = 3
    if max_pages < 1:
        max_pages = 1
    if max_pages > 6:
        max_pages = 6

    try:
        max_chars_per_page = int(args.get("max_chars_per_page", 6000) or 6000)
    except Exception:
        max_chars_per_page = 6000
    if max_chars_per_page < 500:
        max_chars_per_page = 500
    if max_chars_per_page > 20_000:
        max_chars_per_page = 20_000

    save_to_memory = bool(args.get("save_to_memory", True))
    summarize = bool(args.get("summarize", True))

    # 1) Search (Tavily se key; senão DuckDuckGo).
    try:
        from omniscia.modules.integrations.public_apis import _web_search  # type: ignore

        sr = _web_search({"query": query, "max_results": max_results})
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=f"falha na busca: {exc}")

    if getattr(sr, "status", "") != "ok":
        return ToolResult(status="error", error=str(getattr(sr, "error", "falha na busca")))

    try:
        payload = json.loads(str(getattr(sr, "output", "") or "{}"))
    except Exception:
        payload = {}

    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list) or not results:
        return ToolResult(status="ok", output=json.dumps({"query": query, "results": [], "summary": "(sem resultados)"}, ensure_ascii=False))

    items: list[dict[str, Any]] = []
    for r in results[:max_results]:
        if not isinstance(r, dict):
            continue
        url = str(r.get("url", "") or "").strip()
        title = str(r.get("title", "") or "").strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            continue
        items.append({"url": url, "title": title})

    if not items:
        return ToolResult(status="ok", output=json.dumps({"query": query, "results": [], "summary": "(sem resultados)"}, ensure_ascii=False))

    # 2) Fetch pages.
    pages_to_fetch = items[:max_pages]
    fetched: list[dict[str, Any]] = []

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=settings.web_headless)
            page = browser.new_page()

            for it in pages_to_fetch:
                url = str(it.get("url") or "").strip()
                title = str(it.get("title") or "").strip()
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                    text = (page.inner_text("body") or "").strip()
                except Exception:
                    continue

                if not text:
                    continue
                if len(text) > max_chars_per_page:
                    text = text[:max_chars_per_page] + "\n... [truncado]"

                fetched.append({"url": url, "title": title, "text": text})

            browser.close()
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=f"falha abrindo páginas: {exc}")

    # 3) Optional: index in vector memory.
    indexed = 0
    if save_to_memory and getattr(settings, "vector_memory_enabled", False):
        try:
            from omniscia.modules.memory.vector_store import ChromaVectorMemory

            vm = ChromaVectorMemory(
                persist_dir=str(getattr(settings, "vector_memory_persist_dir", "data/chroma") or "data/chroma"),
                collection=str(getattr(settings, "vector_memory_collection", "omniscia_memory") or "omniscia_memory"),
                embed_model=str(getattr(settings, "vector_memory_embed_model", "all-MiniLM-L6-v2") or "all-MiniLM-L6-v2"),
            )

            ts = int(time.time())
            for doc in fetched:
                url = str(doc.get("url") or "").strip()
                title = str(doc.get("title") or "").strip()[:160]
                text = str(doc.get("text") or "").strip()
                if not url or not text:
                    continue
                item_id = _stable_id("web.research", f"{url}|{ts}")
                vm.upsert(
                    item_id=item_id,
                    text=f"WEB_PAGE: {title}\nURL: {url}\n\n{text}",
                    meta={
                        "kind": "web_page",
                        "source": "web.research",
                        "url": url,
                        "title": title,
                        "query": query[:200],
                    },
                )
                indexed += 1
        except Exception:
            indexed = indexed

    # 4) Optional: summarize with LLM.
    summary: str | None = None
    if summarize and fetched:
        try:
            from omniscia.core.chat_llm import chat_reply

            blobs: list[str] = []
            for d in fetched[:max_pages]:
                url = str(d.get("url") or "").strip()
                title = str(d.get("title") or "").strip()
                text = str(d.get("text") or "").strip()
                if not text:
                    continue
                blobs.append(f"FONTE: {title}\nURL: {url}\nTEXTO:\n{text}")
            ctx = "\n\n---\n\n".join(blobs)
            if len(ctx) > 14_000:
                ctx = ctx[:14_000] + "\n... [truncado]"

            prompt = (
                "Você está em modo pesquisa. Resuma em PT-BR, de forma objetiva, e inclua uma seção 'Fontes' listando as URLs usadas. "
                "Não invente fatos que não estejam no texto.\n\n"
                f"PERGUNTA: {query}\n\n"
                f"CONTEÚDO (fontes):\n{ctx}"
            )
            summary = chat_reply(settings, prompt, temperature=0.2, max_chars=2200)
        except Exception:
            summary = None

    out_results: list[dict[str, Any]] = []
    for d in fetched:
        out_results.append(
            {
                "url": d.get("url"),
                "title": d.get("title"),
                "chars": len(str(d.get("text") or "")),
            }
        )

    out = {
        "query": query,
        "searched": len(items),
        "fetched": len(fetched),
        "indexed": indexed,
        "results": out_results,
        "summary": summary,
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


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


def _web_get_links(args: dict[str, Any], *, settings: Settings) -> ToolResult:
    ok, err = _require_playwright()
    if not ok:
        return ToolResult(status="error", error=err)

    url = str(args.get("url", "")).strip()
    max_links = int(args.get("max_links", 50) or 50)

    if not (url.startswith("http://") or url.startswith("https://")):
        return ToolResult(status="error", error="url inválida (use http/https)")

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=settings.web_headless)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)

            anchors = page.query_selector_all("a[href]")
            links: list[dict[str, str]] = []
            seen: set[str] = set()
            for a in anchors:
                href = (a.get_attribute("href") or "").strip()
                text = (a.inner_text() or "").strip()
                if not href:
                    continue

                # Normaliza para absoluto quando possível.
                abs_href = page.evaluate(
                    "(a) => a.href",
                    a,
                )
                abs_href = (abs_href or href or "").strip()
                if abs_href in seen:
                    continue
                seen.add(abs_href)
                links.append({"href": abs_href, "text": text})
                if len(links) >= max_links:
                    break

            browser.close()

        return ToolResult(status="ok", output=json.dumps({"url": url, "links": links}, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))
