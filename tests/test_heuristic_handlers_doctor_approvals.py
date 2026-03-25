from omniscia.core.heuristic_handlers import run_heuristic_handlers


def test_doctor_routes():
    plan = run_heuristic_handlers(user_message="doctor", norm="doctor", context_messages=None)
    assert plan is not None
    assert plan.intent == "core.doctor"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "core.doctor"


def test_approvals_list_routes():
    plan = run_heuristic_handlers(
        user_message="listar aprovações lembradas", norm="listar aprovacoes lembradas", context_messages=None
    )
    assert plan is not None
    assert plan.intent == "core.approvals_list"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "core.approvals_list"


def test_approvals_reset_routes():
    plan = run_heuristic_handlers(
        user_message="resetar aprovações lembradas", norm="resetar aprovacoes lembradas", context_messages=None
    )
    assert plan is not None
    assert plan.intent == "core.approvals_reset"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "core.approvals_reset"


def test_approvals_revoke_contains_routes():
    plan = run_heuristic_handlers(
        user_message="revogar permissoes contendo vscode", norm="revogar permissoes contendo vscode", context_messages=None
    )
    assert plan is not None
    assert plan.intent == "core.approvals_revoke"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "core.approvals_revoke"
    assert plan.tool_calls[0].args.get("contains") == "vscode"
