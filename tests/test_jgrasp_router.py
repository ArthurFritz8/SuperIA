from omniscia.core.config import Settings
from omniscia.core.router import route
from omniscia.core.types import RiskLevel


def test_router_jgrasp_create_program_is_high_and_deterministic():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, "quero que voce crie um programa com codigos no jgrasp")
    assert plan.intent == "jgrasp.create_java_program"
    assert plan.risk == RiskLevel.HIGH
    assert [c.tool_name for c in plan.tool_calls] == ["os.open_app", "jgrasp.create_java_program"]
    assert str(plan.tool_calls[1].args.get("path", "")) == "scratch/HelloWorld.java"


def test_llm_mode_still_prefers_deterministic_jgrasp(monkeypatch):
    import omniscia.core.router as router_mod

    def _boom(*args, **kwargs):  # noqa: ANN001
        raise AssertionError("LLM should not be called for deterministic intents")

    monkeypatch.setattr(router_mod, "_route_with_llm", _boom)

    settings = Settings(router_mode="llm", llm_provider="groq", llm_model="llama-3.3-70b")
    plan = route(settings, "crie um programa funcional no jgrasp")
    assert plan.intent == "jgrasp.create_java_program"
    assert plan.risk == RiskLevel.HIGH


def test_router_jgrasp_project_on_desktop_uses_desktop_prefix():
    settings = Settings(router_mode="heuristic")
    plan = route(
        settings,
        "crie um novo projeto no jgrasp em java, pode salvar na area de trabalho mesmo",
    )
    assert plan.intent == "jgrasp.create_java_program"
    assert plan.risk == RiskLevel.HIGH
    assert [c.tool_name for c in plan.tool_calls] == ["os.open_app", "jgrasp.create_java_program"]
    assert str(plan.tool_calls[1].args.get("path", "")).lower().startswith("desktop:/")


def test_router_jgrasp_matrix_is_deterministic_and_uses_code():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, "ja estou com jgrasp aberto, escreva um codigo de matriz totalmente funcional")
    assert plan.intent == "jgrasp.create_java_program"
    assert plan.risk == RiskLevel.HIGH
    assert [c.tool_name for c in plan.tool_calls] == ["os.open_app", "jgrasp.create_java_program"]
    assert plan.tool_calls[1].args.get("class_name") == "Matriz"
    code = str(plan.tool_calls[1].args.get("code", ""))
    assert "class Matriz" in code
    assert "static void main" in code


def test_router_jgrasp_math_is_deterministic_and_writes_code_only():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, "crie um codigo de matematica no jgrasp, ele ja esta aberto, nao precisa criar arquivo")
    assert plan.intent == "jgrasp.write_code"
    assert plan.risk == RiskLevel.HIGH
    assert [c.tool_name for c in plan.tool_calls] == ["jgrasp.write_code"]
    code = str(plan.tool_calls[0].args.get("code", ""))
    assert "class MatematicaDemo" in code
