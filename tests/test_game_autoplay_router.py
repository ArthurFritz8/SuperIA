from omniscia.core.config import Settings
from omniscia.core.router import route
from omniscia.core.types import RiskLevel


def test_router_generic_game_autoplay_deterministic():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, "jogue qualquer jogo")
    assert plan.intent == "game.autoplay"
    assert plan.risk == RiskLevel.HIGH
    assert [c.tool_name for c in plan.tool_calls] == ["game.calibrate_runner_from_mouse", "game.autoplay"]


def test_router_blocks_competitive_online_automation():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, "jogue um jogo online competitivo")
    assert plan.intent == "chat"
    assert plan.risk == RiskLevel.LOW
    assert plan.tool_calls == []


def test_llm_mode_still_prefers_deterministic_generic_game(monkeypatch):
    import omniscia.core.router as router_mod

    def _boom(*args, **kwargs):  # noqa: ANN001
        raise AssertionError("LLM should not be called for deterministic intents")

    monkeypatch.setattr(router_mod, "_route_with_llm", _boom)

    settings = Settings(router_mode="llm", llm_provider="groq", llm_model="llama-3.3-70b")
    plan = route(settings, "jogue um jogo")
    assert plan.intent in {"game.autoplay", "chat"}
