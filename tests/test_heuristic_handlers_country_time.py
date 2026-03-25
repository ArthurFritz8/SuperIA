from omniscia.core.heuristic_handlers import run_heuristic_handlers


def _route(text: str):
    return run_heuristic_handlers(user_message=text, norm=text.lower(), context_messages=None)


def test_country_info():
    plan = _route("país: brasil")
    assert plan is not None
    assert plan.intent == "data.country_info"
    assert plan.tool_calls[0].tool_name == "data.country_info"


def test_world_time_br_shortcut():
    plan = _route("hora em brasilia")
    assert plan is not None
    assert plan.intent == "time.world_time"
    assert plan.tool_calls[0].args.get("tz") == "America/Sao_Paulo"
