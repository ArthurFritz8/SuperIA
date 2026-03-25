from omniscia.core.heuristic_handlers import run_heuristic_handlers


def test_memory_compact_routes():
    plan = run_heuristic_handlers(
        user_message="compactar memoria", norm="compactar memoria", context_messages=None
    )
    assert plan is not None
    assert plan.intent == "core.memory_compact"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "core.memory_compact"
    assert plan.tool_calls[0].args == {"keep_last": 5000, "archive": True}
