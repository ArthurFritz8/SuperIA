from omniscia.core.config import Settings
from omniscia.core.router import route
from omniscia.core.types import RiskLevel


def test_router_discord_send_message_is_critical():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, 'mandar mensagem para Alice no discord: oi')
    assert plan.intent == "discord.send_message"
    assert plan.risk == RiskLevel.CRITICAL
    assert [c.tool_name for c in plan.tool_calls] == ["os.open_app", "discord.send_message"]


def test_router_click_chat_phrase_routes_to_discord_sender():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, "clique no chat da Alice e mande um oi para ela")
    assert plan.intent == "discord.send_message"
    assert plan.risk == RiskLevel.CRITICAL
    assert [c.tool_name for c in plan.tool_calls] == ["os.open_app", "discord.send_message"]


def test_llm_mode_still_prefers_deterministic_discord_intent(monkeypatch):
    # Se o heurístico produzir um intent determinístico, não deve chamar o LLM.
    import omniscia.core.router as router_mod

    def _boom(*args, **kwargs):  # noqa: ANN001
        raise AssertionError("LLM should not be called for deterministic intents")

    monkeypatch.setattr(router_mod, "_route_with_llm", _boom)

    settings = Settings(router_mode="llm", llm_provider="groq", llm_model="llama-3.3-70b")
    plan = route(settings, "clique no chat da Alice e mande um oi para ela")
    assert plan.intent == "discord.send_message"
    assert plan.risk == RiskLevel.CRITICAL


def test_router_close_discord_is_high():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, "feche o discord")
    assert plan.intent == "os.close_app"
    assert plan.risk == RiskLevel.HIGH
    assert [c.tool_name for c in plan.tool_calls] == ["os.close_app"]


def test_llm_mode_still_prefers_deterministic_close_app(monkeypatch):
    import omniscia.core.router as router_mod

    def _boom(*args, **kwargs):  # noqa: ANN001
        raise AssertionError("LLM should not be called for deterministic intents")

    monkeypatch.setattr(router_mod, "_route_with_llm", _boom)

    settings = Settings(router_mode="llm", llm_provider="groq", llm_model="llama-3.3-70b")
    plan = route(settings, "feche o discord")
    assert plan.intent == "os.close_app"
