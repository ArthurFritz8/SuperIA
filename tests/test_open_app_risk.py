from omniscia.core.brain import _effective_risk_for_plan
from omniscia.core.config import Settings
from omniscia.core.tools import build_default_registry
from omniscia.core.types import Plan, RiskLevel, ToolCall


def test_effective_risk_escalates_for_dangerous_open_app():
    registry = build_default_registry(settings=Settings(), memory_store=None)
    plan = Plan(
        intent="os.open_app",
        user_message="abre o cmd",
        tool_calls=[ToolCall(tool_name="os.open_app", args={"app": "cmd"})],
        risk=RiskLevel.LOW,
        final_response=None,
    )

    effective = _effective_risk_for_plan(plan, registry, settings=Settings())
    assert effective == RiskLevel.CRITICAL


def test_effective_risk_escalates_for_custom_alias_to_dangerous_target():
    settings = Settings(open_apps_json='{"myps": "powershell.exe"}')
    registry = build_default_registry(settings=settings, memory_store=None)
    plan = Plan(
        intent="os.open_app",
        user_message="abre meu powershell",
        tool_calls=[ToolCall(tool_name="os.open_app", args={"app": "myps"})],
        risk=RiskLevel.LOW,
        final_response=None,
    )

    effective = _effective_risk_for_plan(plan, registry, settings=settings)
    assert effective == RiskLevel.CRITICAL


def test_effective_risk_keeps_medium_for_regular_open_app():
    registry = build_default_registry(settings=Settings(), memory_store=None)
    plan = Plan(
        intent="os.open_app",
        user_message="abre a calculadora",
        tool_calls=[ToolCall(tool_name="os.open_app", args={"app": "calculator"})],
        risk=RiskLevel.LOW,
        final_response=None,
    )

    effective = _effective_risk_for_plan(plan, registry, settings=Settings())
    assert effective == RiskLevel.MEDIUM
