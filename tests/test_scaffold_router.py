from omniscia.core.config import Settings
from omniscia.core.router import route
from omniscia.core.types import RiskLevel


def test_router_scaffold_python_project_default():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, "crie um projeto python chamado MeuApp")
    assert plan.intent == "dev.scaffold_project"
    assert plan.risk == RiskLevel.HIGH
    assert [c.tool_name for c in plan.tool_calls] == ["dev.scaffold_project"]
    assert str(plan.tool_calls[0].args.get("name")).lower().startswith("meuapp")


def test_router_help_maps_to_core_help():
    settings = Settings(router_mode="heuristic")
    plan = route(settings, "ajuda")
    assert plan.intent == "core.help"
    assert [c.tool_name for c in plan.tool_calls] == ["core.help"]
