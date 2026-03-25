import asyncio

from omniscia.core.config import Settings
from omniscia.core.tools import ToolRegistry


def test_web_tools_register_async_fn(monkeypatch):
    import omniscia.modules.web.tooling as wt

    # Force Playwright missing path (default), but we only test registration and selection.
    r = ToolRegistry()
    s = Settings()
    wt.register_web_tools(r, s)

    # Ensure async variants are present for the key tools.
    for name in ["web.get_page_text", "web.screenshot", "web.get_links", "web.research"]:
        spec = r.get(name)
        assert spec is not None
        assert spec.async_fn is not None


def test_web_tool_async_returns_error_without_playwright(monkeypatch):
    import omniscia.modules.web.tooling as wt

    # Make sure _require_playwright returns missing.
    monkeypatch.setattr(wt, "_require_playwright", lambda: (False, "no playwright"))

    out = asyncio.run(wt._web_get_page_text_async({"url": "https://example.com"}, settings=Settings()))
    assert out.status == "error"
    assert "playwright" in (out.error or "") or "no playwright" in (out.error or "")
