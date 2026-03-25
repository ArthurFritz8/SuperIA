from omniscia.core.heuristic_handlers import run_heuristic_handlers
from omniscia.core.types import RiskLevel


def _route(text: str):
    return run_heuristic_handlers(user_message=text, norm=text.lower(), context_messages=None)


def test_screen_rewind_status():
    plan = _route("status do monitoramento da tela")
    assert plan is not None
    assert plan.intent == "vision.rewind_status"
    assert plan.tool_calls[0].tool_name == "screen.rewind_status"
    assert plan.risk == RiskLevel.LOW


def test_screen_rewind_start_requires_approval():
    plan = _route("iniciar monitoramento contínuo da tela")
    assert plan is not None
    assert plan.intent == "vision.start_rewind"
    assert plan.tool_calls[0].tool_name == "screen.rewind_start"
    assert plan.risk == RiskLevel.HIGH


def test_screen_rewind_stop_requires_approval():
    plan = _route("parar rewind da tela")
    assert plan is not None
    assert plan.intent == "vision.stop_rewind"
    assert plan.tool_calls[0].tool_name == "screen.rewind_stop"
    assert plan.risk == RiskLevel.HIGH


def test_screenshot_intent():
    plan = _route("tire uma captura de tela")
    assert plan is not None
    assert plan.intent == "vision.screenshot"
    assert plan.tool_calls[0].tool_name == "screen.screenshot"
    assert plan.risk == RiskLevel.MEDIUM
