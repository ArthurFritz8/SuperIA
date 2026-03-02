from omniscia.core.config import Settings
from omniscia.core.router import route


def test_router_omega_on_is_deterministic():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, "ativa o modo omega")
    assert plan.intent == "core.omega_on"
    assert plan.tool_calls == []


def test_router_omega_off_is_deterministic():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, "desliga o jarvis")
    assert plan.intent == "core.omega_off"
    assert plan.tool_calls == []
