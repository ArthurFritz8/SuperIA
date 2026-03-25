from omniscia.core.heuristic_handlers import run_heuristic_handlers


def _route(text: str, ctx=None):
    return run_heuristic_handlers(user_message=text, norm=text.lower(), context_messages=ctx)


def test_pi_network_wikipedia_summary():
    plan = _route("você conhece a pi network?")
    assert plan is not None
    assert plan.intent == "knowledge.wikipedia_summary"
    assert plan.tool_calls
    assert plan.tool_calls[0].tool_name == "knowledge.wikipedia_summary"


def test_crypto_chart_from_context_subject():
    ctx = [{"role": "user", "content": "Você conhece a moeda Pi Network?"}]
    plan = _route("estude o gráfico da moeda", ctx=ctx)
    assert plan is not None
    assert plan.intent == "finance.crypto_market_chart"
    assert plan.tool_calls
    assert plan.tool_calls[0].tool_name == "finance.crypto_market_chart"
