from omniscia.core.heuristic_handlers import run_heuristic_handlers


def _route(text: str, ctx=None):
    return run_heuristic_handlers(user_message=text, norm=text.lower(), context_messages=ctx)


def test_crypto_intel_report_routes_both():
    plan = _route("gera um relatório crypto intel")
    assert plan is not None
    assert plan.intent == "crypto.intel_report"
    assert plan.tool_calls
    assert plan.tool_calls[0].tool_name == "crypto.intel_report"
    assert plan.tool_calls[0].args.get("mode") == "both"


def test_crypto_intel_report_routes_airdrops_only():
    plan = _route("relatório de airdrops e oportunidades")
    assert plan is not None
    assert plan.intent == "crypto.intel_report"
    assert plan.tool_calls
    assert plan.tool_calls[0].args.get("mode") == "airdrops"


def test_crypto_intel_report_routes_memecoins_solana():
    plan = _route("report memecoins solana")
    assert plan is not None
    assert plan.intent == "crypto.intel_report"
    assert plan.tool_calls
    assert plan.tool_calls[0].args.get("mode") == "memecoins"
    assert plan.tool_calls[0].args.get("chain") == "solana"
