from omniscia.core.config import Settings
from omniscia.core.router import route
from omniscia.core.types import RiskLevel


def test_router_compile_project_is_deterministic_and_safe():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, "compila o projeto")
    assert plan.intent == "dev.exec"
    assert plan.risk == RiskLevel.HIGH
    assert [c.tool_name for c in plan.tool_calls] == ["dev.exec", "dev.exec"]
    commands = [str(c.args.get("command", "")) for c in plan.tool_calls]
    assert "python -m compileall -q omniscia" in commands
    assert "python -m pytest -q" in commands


def test_llm_mode_still_prefers_deterministic_compile(monkeypatch):
    import omniscia.core.router as router_mod

    def _boom(*args, **kwargs):  # noqa: ANN001
        raise AssertionError("LLM should not be called for deterministic intents")

    monkeypatch.setattr(router_mod, "_route_with_llm", _boom)

    settings = Settings(router_mode="llm", llm_provider="groq", llm_model="llama-3.3-70b")
    plan = route(settings, "compilar o projeto")
    assert plan.intent == "dev.exec"
