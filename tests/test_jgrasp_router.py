from omniscia.core.config import Settings
from omniscia.core.router import route
from omniscia.core.types import RiskLevel


def test_router_jgrasp_create_program_is_high_and_deterministic():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, "quero que voce crie um programa simples (hello world) no jgrasp")
    assert plan.intent == "jgrasp.create_java_program"
    assert plan.risk == RiskLevel.HIGH
    assert [c.tool_name for c in plan.tool_calls] == ["os.open_app", "jgrasp.create_java_program"]
    assert str(plan.tool_calls[1].args.get("path", "")) == "scratch/HelloWorld.java"


def test_llm_mode_calls_llm_for_nontrivial_jgrasp(monkeypatch):
    import omniscia.core.router as router_mod

    called = {"n": 0}

    def _fake_llm(settings, messages):  # noqa: ANN001
        called["n"] += 1
        return router_mod.Plan(
            intent="jgrasp.create_java_program",
            user_message=str(messages[-1]["content"]),
            risk=router_mod.RiskLevel.HIGH,
            tool_calls=[
                router_mod.ToolCall(tool_name="os.open_app", args={"app": "jgrasp"}),
                router_mod.ToolCall(
                    tool_name="jgrasp.create_java_program",
                    args={
                        "path": "scratch/Programa.java",
                        "class_name": "Programa",
                        "code": "public class Programa { public static void main(String[] args) { System.out.println(\"ok\"); } }",
                        "open_in_jgrasp": True,
                        "settle_ms": 900,
                    },
                ),
            ],
            final_response="Ok — vou criar o programa no jGRASP (requer aprovação).",
        )

    monkeypatch.setattr(router_mod, "_route_with_llm_messages", _fake_llm)

    settings = Settings(router_mode="llm", llm_provider="groq", llm_model="llama-3.3-70b")
    plan = route(settings, "crie um programa funcional no jgrasp")
    assert plan.intent == "jgrasp.create_java_program"
    assert plan.risk == RiskLevel.HIGH
    assert called["n"] >= 1


def test_router_jgrasp_project_on_desktop_uses_desktop_prefix():
    settings = Settings(router_mode="heuristic")
    plan = route(
        settings,
        "crie um novo projeto no jgrasp em java, pode salvar na area de trabalho mesmo",
    )
    # No modo heurístico, sem pedir explicitamente 'simples/hello world', isso vira chat.
    assert plan.intent == "chat"
    assert plan.tool_calls == []


def test_router_jgrasp_matrix_in_heuristic_falls_back_to_chat():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, "ja estou com jgrasp aberto, escreva um codigo de matriz totalmente funcional")
    assert plan.intent == "chat"
    assert plan.tool_calls == []


def test_router_jgrasp_math_in_heuristic_falls_back_to_chat():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, "crie um codigo de matematica no jgrasp, ele ja esta aberto, nao precisa criar arquivo")
    assert plan.intent == "chat"
    assert plan.tool_calls == []


def test_router_jgrasp_conta_in_heuristic_falls_back_to_chat():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, "quero que voce crie a conta tambem no jgrasp")
    assert plan.intent == "chat"
    assert plan.tool_calls == []


def test_router_modify_and_make_matrix_in_heuristic_falls_back_to_chat():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, "modifique o codigo, apague o codigo e faça uma matriz agora")
    assert plan.intent == "chat"
    assert plan.tool_calls == []
