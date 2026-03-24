from __future__ import annotations

from omniscia.core.config import Settings
from omniscia.core.router import route
from omniscia.core.types import RiskLevel


def test_weather_route_open_meteo():
    settings = Settings.load()
    plan = route(settings, "clima em São Paulo")
    assert plan.intent == "data.weather"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "data.weather_open_meteo"
    assert plan.risk == RiskLevel.MEDIUM


def test_crypto_price_route():
    settings = Settings.load()
    plan = route(settings, "qual o preço do bitcoin agora?")
    assert plan.intent == "finance.crypto_price"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "finance.crypto_price"
    assert plan.risk == RiskLevel.MEDIUM


def test_wikipedia_route():
    settings = Settings.load()
    plan = route(settings, "wikipedia: Alan Turing")
    assert plan.intent == "knowledge.wikipedia_summary"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "knowledge.wikipedia_summary"
    assert plan.risk == RiskLevel.MEDIUM
