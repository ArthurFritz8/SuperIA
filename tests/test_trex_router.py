from omniscia.core.config import Settings
from omniscia.core.router import route
from omniscia.core.types import RiskLevel


def test_router_trex_autoplay_is_deterministic_in_heuristic_mode():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, "joga o joguinho do t-rex")
    assert plan.intent == "game.trex_autoplay"
    assert plan.risk == RiskLevel.HIGH
    assert [c.tool_name for c in plan.tool_calls] == ["game.trex_autoplay"]


def test_llm_mode_still_prefers_deterministic_trex(monkeypatch):
    import omniscia.core.router as router_mod

    def _boom(*args, **kwargs):  # noqa: ANN001
        raise AssertionError("LLM should not be called for deterministic intents")

    monkeypatch.setattr(router_mod, "_route_with_llm", _boom)

    settings = Settings(router_mode="llm", llm_provider="groq", llm_model="llama-3.3-70b")
    plan = route(settings, "jogue o trex")
    assert plan.intent == "game.trex_autoplay"
