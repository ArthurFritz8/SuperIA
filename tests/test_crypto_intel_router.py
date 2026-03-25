from omniscia.core.heuristic_handlers import run_heuristic_handlers


def _route(text: str, ctx=None):
    return run_heuristic_handlers(user_message=text, norm=text.lower(), context_messages=ctx)


def test_airdrop_intel_routes():
    plan = _route("me mande airdrops ativos agora")
    assert plan is not None
    assert plan.intent == "crypto.airdrops_intel"
    assert plan.tool_calls
    assert any(tc.tool_name == "finance.defillama_protocols" for tc in plan.tool_calls)


def test_memecoin_intel_routes_default():
    plan = _route("quero memecoins em pre lancamento")
    assert plan is not None
    assert plan.intent == "crypto.memecoin_intel"
    assert plan.tool_calls
    assert any(tc.tool_name.startswith("finance.dexscreener_") for tc in plan.tool_calls)


def test_memecoin_intel_routes_chain_solana():
    plan = _route("memecoin stealth launch na solana")
    assert plan is not None
    assert plan.intent == "crypto.memecoin_intel"
    assert plan.tool_calls
    assert plan.tool_calls[0].tool_name == "finance.dexscreener_chain_discovery"
    assert plan.tool_calls[0].args.get("chain") == "solana"
