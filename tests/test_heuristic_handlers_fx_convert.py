from omniscia.core.heuristic_handlers import run_heuristic_handlers


def _route(text: str):
    return run_heuristic_handlers(user_message=text, norm=text.lower(), context_messages=None)


def test_fx_convert():
    plan = _route("converter 10 usd para brl")
    assert plan is not None
    assert plan.intent == "finance.fx_convert"
    assert plan.tool_calls[0].tool_name == "finance.fx_convert"
    assert plan.tool_calls[0].args.get("amount") == 10.0
    assert plan.tool_calls[0].args.get("from") == "USD"
    assert plan.tool_calls[0].args.get("to") == "BRL"
