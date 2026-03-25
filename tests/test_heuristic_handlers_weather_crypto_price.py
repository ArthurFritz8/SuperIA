from omniscia.core.heuristic_handlers import run_heuristic_handlers


def _route(text: str):
    return run_heuristic_handlers(user_message=text, norm=text.lower(), context_messages=None)


def test_weather_explicit_city():
    plan = _route("clima em São Paulo")
    assert plan is not None
    assert plan.intent == "data.weather"
    assert plan.tool_calls[0].tool_name == "data.weather_open_meteo"


def test_crypto_price_bitcoin():
    plan = _route("preço do bitcoin")
    assert plan is not None
    assert plan.intent == "finance.crypto_price"
    assert plan.tool_calls[0].tool_name == "finance.crypto_price"
    assert plan.tool_calls[0].args.get("asset") in {"bitcoin", "btc"}
