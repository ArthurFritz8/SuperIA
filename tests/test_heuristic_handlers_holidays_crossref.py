from omniscia.core.heuristic_handlers import run_heuristic_handlers


def _route(text: str):
    return run_heuristic_handlers(user_message=text, norm=text.lower(), context_messages=None)


def test_holidays():
    plan = _route("feriados 2026 BR")
    assert plan is not None
    assert plan.intent == "calendar.holidays"
    assert plan.tool_calls[0].tool_name == "calendar.holidays"
    assert plan.tool_calls[0].args.get("year") == 2026
    assert plan.tool_calls[0].args.get("country_code") == "BR"


def test_crossref():
    plan = _route("crossref: transformers attention")
    assert plan is not None
    assert plan.intent == "papers.crossref_search"
    assert plan.tool_calls[0].tool_name == "papers.crossref_search"
    assert plan.tool_calls[0].args.get("rows") == 5
