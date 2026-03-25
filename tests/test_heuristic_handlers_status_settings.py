from omniscia.core.heuristic_handlers import run_heuristic_handlers


def test_status_settings_routes_to_show_settings():
    plan = run_heuristic_handlers(user_message="settings", norm="settings", context_messages=None)
    assert plan is not None
    assert plan.intent == "core.show_settings"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "core.show_settings"
    assert plan.tool_calls[0].args == {}


def test_status_vendor_github():
    plan = run_heuristic_handlers(user_message="status do github", norm="status do github", context_messages=None)
    assert plan is not None
    assert plan.intent == "status.github"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "status.github"
    assert plan.tool_calls[0].args == {}


def test_status_vendor_openai():
    plan = run_heuristic_handlers(user_message="openai status", norm="openai status", context_messages=None)
    assert plan is not None
    assert plan.intent == "status.openai"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "status.openai"
    assert plan.tool_calls[0].args == {}
