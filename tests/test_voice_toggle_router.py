from omniscia.core.config import Settings
from omniscia.core.router import route
from omniscia.core.types import RiskLevel


def test_router_voice_off_deterministic():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, "silenciar")
    assert plan.intent == "core.voice_off"
    assert plan.risk == RiskLevel.LOW
    assert plan.tool_calls == []


def test_router_voice_on_deterministic():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, "ativar voz")
    assert plan.intent == "core.voice_on"
    assert plan.risk == RiskLevel.LOW
    assert plan.tool_calls == []


def test_llm_mode_prefers_deterministic_voice_toggle(monkeypatch):
    import omniscia.core.router as router_mod

    def _boom(*args, **kwargs):  # noqa: ANN001
        raise AssertionError("LLM should not be called for deterministic intents")

    monkeypatch.setattr(router_mod, "_route_with_llm", _boom)

    settings = Settings(router_mode="llm", llm_provider="groq", llm_model="llama-3.3-70b")
    plan = route(settings, "silenciar")
    assert plan.intent == "core.voice_off"
