import json
import asyncio

from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult


def test_registry_prefers_async_fn(monkeypatch):
    called = {"async": 0, "sync": 0}

    async def afn(args):
        called["async"] += 1
        return ToolResult(status="ok", output=json.dumps({"ok": True}))

    def sfn(args):
        called["sync"] += 1
        return ToolResult(status="ok", output=json.dumps({"ok": False}))

    r = ToolRegistry()
    r.register(ToolSpec(name="x.test", description="", risk="LOW", fn=sfn, async_fn=afn))

    out = asyncio.run(r.run_async("x.test", {}))
    assert out.status == "ok"
    assert out.output is not None
    assert json.loads(out.output)["ok"] is True
    assert called["async"] == 1
    assert called["sync"] == 0


def test_public_api_async_wrappers(monkeypatch):
    # Import inside test so monkeypatching applies cleanly.
    import omniscia.modules.integrations.public_apis as pa

    async def fake_http_json_async(*, method, url, params=None, json_body=None, headers=None, timeout_s=12.0):
        # Return a minimal Wikipedia-like payload
        if "wikipedia.org" in url:
            return (
                {
                    "title": "Python",
                    "extract": "Uma linguagem.",
                    "content_urls": {"desktop": {"page": "https://pt.wikipedia.org/wiki/Python"}},
                },
                None,
            )
        # CoinGecko simple price
        if "coingecko.com" in url:
            return ({"bitcoin": {"brl": 1.0, "usd": 1.0}}, None)
        # Tavily
        if "tavily.com" in url:
            return ({"query": "x", "results": []}, None)
        # Open-Meteo geocoding
        if "geocoding-api.open-meteo.com" in url:
            return ({"results": [{"name": "X", "admin1": "Y", "country": "BR", "latitude": -1.0, "longitude": -2.0}]}, None)
        # Open-Meteo forecast
        if "api.open-meteo.com" in url:
            return ({"current": {"temperature_2m": 25.0}}, None)
        # Nominatim search
        if "nominatim.openstreetmap.org/search" in url:
            return ([{"display_name": "Z", "lat": "-1.0", "lon": "-2.0", "type": "city", "class": "place", "address": {}}], None)
        # Nominatim reverse
        if "nominatim.openstreetmap.org/reverse" in url:
            return ({"display_name": "Z", "address": {"country": "BR"}}, None)
        # Frankfurter
        if "api.frankfurter.app" in url:
            return ({"date": "2020-01-01", "rates": {"BRL": 5.0}}, None)
        return (None, "unexpected url")

    monkeypatch.setattr(pa, "_http_json_async", fake_http_json_async)

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, *args, **kwargs):
            class R:
                status_code = 200
                text = """<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns='http://www.w3.org/2005/Atom'>
  <entry>
    <title>Paper</title>
    <summary>Sum</summary>
    <published>2020-01-01</published>
    <author><name>A</name></author>
    <link rel='alternate' href='https://arxiv.org/abs/1'/>
  </entry>
</feed>"""

            return R()

    # Patch AsyncClient used by arxiv async path
    monkeypatch.setattr(pa.httpx, "AsyncClient", FakeAsyncClient)

    # Wikipedia
    w = asyncio.run(pa._wikipedia_summary_async({"title": "Python", "lang": "pt"}))
    assert isinstance(w, ToolResult)
    assert w.status == "ok"
    assert w.output is not None
    wp = json.loads(w.output)
    assert wp["title"]
    assert "summary" in wp

    # Crypto price: avoid hitting the real resolver by forcing alias
    c = asyncio.run(pa._crypto_price_async({"asset": "bitcoin", "vs": "brl,usd"}))
    assert c.status == "ok"
    assert c.output is not None
    cp = json.loads(c.output)
    assert cp["coin_id"] == "bitcoin"

    # Web search (Tavily path): only when env key exists; we fake it.
    monkeypatch.setenv("OMNI_TAVILY_API_KEY", "k")
    s = asyncio.run(pa._web_search_async({"query": "x", "max_results": 2}))
    assert s.status == "ok"
    assert s.output is not None
    sp = json.loads(s.output)
    assert "results" in sp or "query" in sp

    # Weather
    wx = asyncio.run(pa._weather_open_meteo_async({"city": "Sao Paulo", "lang": "pt", "country_code": "BR"}))
    assert wx.status == "ok"
    assert wx.output is not None
    wxp = json.loads(wx.output)
    assert "place" in wxp and "current" in wxp

    # Geo geocode
    gg = asyncio.run(pa._geo_geocode_async({"query": "X", "lang": "pt"}))
    assert gg.status == "ok"
    assert gg.output is not None
    ggp = json.loads(gg.output)
    assert ggp["results"]

    # Geo reverse
    gr = asyncio.run(pa._geo_reverse_geocode_async({"lat": -1.0, "lon": -2.0, "lang": "pt"}))
    assert gr.status == "ok"
    assert gr.output is not None
    grp = json.loads(gr.output)
    assert "display_name" in grp

    # FX
    fx = asyncio.run(pa._fx_convert_async({"amount": 1, "from": "USD", "to": "BRL"}))
    assert fx.status == "ok"
    assert fx.output is not None
    fxp = json.loads(fx.output)
    assert fxp["result"] == 5.0

    # arXiv
    ax = asyncio.run(pa._arxiv_search_async({"query": "x", "max_results": 1}))
    assert ax.status == "ok"
    assert ax.output is not None
    axp = json.loads(ax.output)
    assert axp["results"]
