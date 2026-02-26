from omniscia.core.config import Settings
from omniscia.core.router import route
from omniscia.core.types import Plan, RiskLevel, ToolCall


def test_llm_guard_rejects_discord_when_not_requested(monkeypatch):
    import omniscia.core.router as router_mod

    def _fake_llm_plan(*args, **kwargs):  # noqa: ANN001
        return Plan(
            intent="oops",
            user_message="x",
            risk=RiskLevel.CRITICAL,
            tool_calls=[ToolCall(tool_name="discord.send_message", args={"to": "alguem", "message": "oi"})],
            final_response="x",
        )

    monkeypatch.setattr(router_mod, "_route_with_llm", _fake_llm_plan)

    settings = Settings(router_mode="llm", llm_provider="groq", llm_model="llama-3.3-70b")
    # User did not request Discord.
    plan = route(settings, "crie um codigo no jgrasp")
    assert plan.intent != "oops"
    assert all((c.tool_name or "") != "discord.send_message" for c in plan.tool_calls)
