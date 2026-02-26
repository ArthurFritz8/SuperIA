from omniscia.core.config import Settings
from omniscia.core.router import route
from omniscia.core.types import RiskLevel


def test_router_jgrasp_create_program_is_high_and_deterministic():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, "quero que voce crie um programa com codigos no jgrasp")
    assert plan.intent == "jgrasp.create_java_program"
    assert plan.risk == RiskLevel.HIGH
    assert [c.tool_name for c in plan.tool_calls] == ["os.open_app", "jgrasp.create_java_program"]


def test_llm_mode_still_prefers_deterministic_jgrasp(monkeypatch):
    import omniscia.core.router as router_mod

    def _boom(*args, **kwargs):  # noqa: ANN001
        raise AssertionError("LLM should not be called for deterministic intents")

    monkeypatch.setattr(router_mod, "_route_with_llm", _boom)

    settings = Settings(router_mode="llm", llm_provider="groq", llm_model="llama-3.3-70b")
    plan = route(settings, "crie um programa funcional no jgrasp")
    assert plan.intent == "jgrasp.create_java_program"
    assert plan.risk == RiskLevel.HIGH
