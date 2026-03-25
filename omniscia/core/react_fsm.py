"""ReAct FSM (execução de plano com replanning).

Este módulo contém a lógica do loop ReAct em modo FSM explícita.
Objetivo:
- Reduzir tamanho do brain.py (god function)
- Facilitar testes/observabilidade
- Permitir evolução incremental para async

Importante:
- Deve preservar comportamento e mensagens do CLI.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from enum import Enum, auto

from rich.console import Console
from rich.panel import Panel

from omniscia.core.approvals import ApprovalStore
from omniscia.core.config import Settings
from omniscia.core.policy import PolicyEngine
from omniscia.core.runlog import RunLogger
from omniscia.core.snapshots import SnapshotManager
from omniscia.core.types import Plan, RiskLevel, ToolCall
from omniscia.core.hitl import require_approval


class ReactState(Enum):
    INIT_STEP = auto()
    PREFLIGHT = auto()
    POLICY = auto()
    HITL = auto()
    SNAPSHOT = auto()
    RUN_TOOL = auto()
    SHORTCIRCUIT = auto()
    TRACE_AND_CHECKPOINT = auto()
    REPLAN = auto()


def execute_plan_react(
    console: Console,
    settings: Settings,
    registry,
    plan: Plan,
    memory,
    approvals: ApprovalStore | None = None,
    remember: bool = False,
    *,
    worker_mgr=None,
    policy: PolicyEngine | None = None,
    snapshot_mgr: SnapshotManager | None = None,
    runlog: RunLogger | None = None,
    normalize_plan_args=None,
    normalize_tool_args=None,
    preflight_validate_plan=None,
    effective_risk_for_plan=None,
    run_tool_with_retry=None,
    build_router_context_messages=None,
    route_llm=None,
    route_with_registry=None,
):
    """Execução ReAct síncrona.

    Dependências funcionais são injetadas para evitar import cycles com brain.py.
    """

    assert normalize_plan_args is not None
    assert preflight_validate_plan is not None
    assert effective_risk_for_plan is not None
    assert run_tool_with_retry is not None
    assert build_router_context_messages is not None
    assert route_llm is not None
    assert route_with_registry is not None

    run = None
    rl = None
    if getattr(settings, "runlog_enabled", True):
        try:
            rl = runlog or RunLogger(base_dir=str(getattr(settings, "runlog_dir", "data/runs") or "data/runs"))
            run = rl.start(intent=str(plan.intent or "react"))
            rl.append(
                run,
                "plan",
                {
                    "intent": plan.intent,
                    "risk": str(plan.risk),
                    "tool_calls": [c.model_dump() for c in plan.tool_calls],
                },
            )
        except Exception:
            rl = None
            run = None

    max_steps = int(getattr(settings, "autonomy_max_steps", 12) or 12) if getattr(settings, "autonomy_enabled", False) else 6
    checkpoint_every = int(getattr(settings, "autonomy_checkpoint_every", 4) or 4)
    if checkpoint_every < 1:
        checkpoint_every = 1

    original_user_message = (plan.user_message or "").strip()
    current_plan = plan

    single_shot_tools = {"edu.pdf_word_autofill", "finance.crypto_market_chart"}
    trace_messages: list[dict[str, str]] = []

    for step in range(1, max_steps + 1):
        state = ReactState.INIT_STEP
        call: ToolCall | None = None
        normalized_plan: Plan | None = None
        result = None

        while True:
            if state is ReactState.INIT_STEP:
                if not current_plan.tool_calls:
                    text = (current_plan.final_response or "").strip() or "Feito."
                    console.print(f"Agente> {text}")
                    memory.append("agent_response", {"text": text})
                    return text

                call = current_plan.tool_calls[0]
                state = ReactState.PREFLIGHT
                continue

            if state is ReactState.PREFLIGHT:
                assert call is not None
                step_plan = current_plan.model_copy(update={"tool_calls": [call]})
                effective_risk = effective_risk_for_plan(step_plan, registry, settings=settings)
                effective_plan = step_plan if effective_risk == step_plan.risk else step_plan.model_copy(update={"risk": effective_risk})
                normalized_plan, _ = normalize_plan_args(effective_plan, settings=settings)

                preflight_error = preflight_validate_plan(normalized_plan, registry, settings=settings)
                if preflight_error:
                    console.print(f"[red]Preflight error:[/red] {preflight_error}")
                    console.print("Agente> Não executei por segurança.")
                    if rl is not None and run is not None:
                        try:
                            rl.append(run, "preflight_error", {"error": preflight_error, "step": step})
                        except Exception:
                            pass
                    return None

                if getattr(settings, "ui_show_react_steps", False):
                    assert normalized_plan is not None
                    console.print(
                        Panel.fit(
                            f"ReAct step {step}/{max_steps}\nTool: {call.tool_name}\nRisk: {normalized_plan.risk}",
                            title="Plano",
                        )
                    )

                state = ReactState.POLICY
                continue

            if state is ReactState.POLICY:
                assert call is not None
                assert normalized_plan is not None

                if getattr(settings, "policy_enabled", True):
                    try:
                        eng = policy
                        if eng is None:
                            eng = PolicyEngine(path=str(getattr(settings, "policy_path", "data/policy.json") or "data/policy.json"))
                            eng.load()
                        ok, decisions = eng.decide_plan([call], plan_risk=normalized_plan.risk)
                        if not ok:
                            denied = [d for d in decisions if not d.allowed]
                            reason = denied[0].reason if denied else "policy denied"
                            console.print(Panel.fit(f"Policy bloqueou a tool.\nMotivo: {reason}", title="Policy"))
                            memory.append("policy_denied", {"tool": call.tool_name, "reason": reason, "step": step})
                            if rl is not None and run is not None:
                                try:
                                    rl.append(run, "policy_denied", {"tool": call.tool_name, "reason": reason, "step": step})
                                except Exception:
                                    pass
                            return None
                    except Exception as exc:  # noqa: BLE001
                        memory.append("policy_error", {"error": str(exc), "step": step})

                state = ReactState.HITL
                continue

            if state is ReactState.HITL:
                assert normalized_plan is not None
                assert call is not None

                if not require_approval(
                    normalized_plan,
                    enabled=settings.hitl_enabled,
                    min_risk=settings.hitl_min_risk,
                    require_token=settings.hitl_require_token,
                    remember=remember,
                    approvals=approvals,
                ):
                    console.print("Agente> Ok, não vou executar isso.")
                    if rl is not None and run is not None:
                        try:
                            rl.append(run, "hitl_denied", {"tool": call.tool_name, "step": step})
                        except Exception:
                            pass
                    return None

                state = ReactState.SNAPSHOT
                continue

            if state is ReactState.SNAPSHOT:
                assert normalized_plan is not None
                assert call is not None

                if (
                    getattr(settings, "snapshots_enabled", True)
                    and getattr(settings, "snapshots_auto_before_high_risk", True)
                    and normalized_plan.risk in {RiskLevel.HIGH, RiskLevel.CRITICAL}
                ):
                    try:
                        mgr = snapshot_mgr
                        if mgr is None:
                            mgr = SnapshotManager(snapshots_dir=str(getattr(settings, "snapshots_dir", "data/snapshots") or "data/snapshots"))
                        info = mgr.create(label=f"react_{call.tool_name}"[:40])
                        memory.append("snapshot_created", {"snapshot_id": info.snapshot_id, "tool": call.tool_name, "step": step})
                        if rl is not None and run is not None:
                            try:
                                rl.append(run, "snapshot_created", {"snapshot_id": info.snapshot_id, "tool": call.tool_name, "step": step})
                            except Exception:
                                pass
                    except Exception:
                        pass

                state = ReactState.RUN_TOOL
                continue

            if state is ReactState.RUN_TOOL:
                assert call is not None

                result = run_tool_with_retry(console, settings, registry, call, memory)
                if rl is not None and run is not None:
                    try:
                        rl.append(
                            run,
                            "tool_result",
                            {
                                "tool": call.tool_name,
                                "args": call.args,
                                "status": result.status,
                                "output": result.output,
                                "error": result.error,
                                "step": step,
                            },
                        )
                    except Exception:
                        pass

                if result.status == "error":
                    console.print(f"[red]Tool error:[/red] {call.tool_name}: {result.error}")

                if getattr(settings, "ui_show_tool_outputs", True) and result.output:
                    out = result.output.strip()
                    if len(out) > 2000:
                        out = out[:2000] + "\n... [truncado]"
                    console.print(Panel(out, title=f"Tool: {call.tool_name}"))

                state = ReactState.SHORTCIRCUIT
                continue

            if state is ReactState.SHORTCIRCUIT:
                assert call is not None
                assert result is not None

                if result.status == "ok" and call.tool_name in single_shot_tools and (current_plan.intent or "").strip() == call.tool_name:
                    text = (result.output or "").strip() or "Feito."
                    console.print(f"Agente> {text}")
                    memory.append("agent_response", {"text": text})
                    return text

                state = ReactState.TRACE_AND_CHECKPOINT
                continue

            if state is ReactState.TRACE_AND_CHECKPOINT:
                assert call is not None
                assert result is not None

                out_short = (result.output or "").strip()
                if len(out_short) > 1200:
                    out_short = out_short[:1200] + "\n... [truncado]"
                err_short = str(result.error or "").strip()
                if len(err_short) > 800:
                    err_short = err_short[:800] + "... [truncado]"

                trace = {"tool": call.tool_name, "args": call.args, "status": result.status, "output": out_short, "error": err_short}
                trace_messages.append({"role": "assistant", "content": "TOOL_RESULT " + json.dumps(trace, ensure_ascii=False)})
                if len(trace_messages) > 8:
                    trace_messages = trace_messages[-8:]

                if getattr(settings, "autonomy_enabled", False) and checkpoint_every and (step % checkpoint_every == 0) and step < max_steps:
                    memory.append(
                        "autonomy_checkpoint",
                        {"step": step, "max_steps": max_steps, "last_tool": call.tool_name, "last_status": result.status},
                    )
                    console.print(
                        Panel.fit(
                            f"Checkpoint: step {step}/{max_steps}\nÚltima tool: {call.tool_name} ({result.status})",
                            title="Autonomia",
                        )
                    )

                if len(current_plan.tool_calls) > 1:
                    trace_messages.append(
                        {"role": "assistant", "content": "HINT: o plano anterior continha mais tool_calls; replaine considerando o objetivo original."}
                    )
                    if len(trace_messages) > 8:
                        trace_messages = trace_messages[-8:]

                state = ReactState.REPLAN
                continue

            if state is ReactState.REPLAN:
                conv_ctx = build_router_context_messages(memory, current_user_message=original_user_message, limit_messages=8)
                replanning_ctx = conv_ctx + trace_messages
                new_plan = route_llm(settings, original_user_message, context_messages=replanning_ctx, registry=registry)
                if new_plan is None:
                    safe_settings = replace(settings, router_mode="heuristic")
                    new_plan = route_with_registry(
                        safe_settings,
                        original_user_message,
                        registry=registry,
                        context_messages=replanning_ctx,
                    )

                memory.append(
                    "plan",
                    {"intent": new_plan.intent, "risk": str(new_plan.risk), "tool_calls": [c.model_dump() for c in new_plan.tool_calls]},
                )
                current_plan = new_plan
                break

            raise RuntimeError(f"Unhandled ReAct state: {state}")

    console.print("Agente> Parei para não entrar em loop. Se quiser, descreva o que você viu/obteve e eu continuo.")
    memory.append("agent_response", {"text": "Parei para não entrar em loop. Se quiser, descreva o que você viu/obteve e eu continuo."})
    return "Parei para não entrar em loop. Se quiser, descreva o que você viu/obteve e eu continuo."


async def execute_plan_react_async(
    console: Console,
    settings: Settings,
    registry,
    plan: Plan,
    memory,
    approvals: ApprovalStore | None = None,
    remember: bool = False,
    *,
    worker_mgr=None,
    policy: PolicyEngine | None = None,
    snapshot_mgr: SnapshotManager | None = None,
    runlog: RunLogger | None = None,
    metrics=None,
    normalize_plan_args=None,
    preflight_validate_plan=None,
    effective_risk_for_plan=None,
    run_tool_with_retry_async=None,
    build_router_context_messages=None,
    route_llm_async=None,
    route_with_registry_async=None,
):
    """Execução ReAct async.

    Mesma lógica da versão sync, mas tool execution e replanning são await.
    """

    assert normalize_plan_args is not None
    assert preflight_validate_plan is not None
    assert effective_risk_for_plan is not None
    assert run_tool_with_retry_async is not None
    assert build_router_context_messages is not None
    assert route_llm_async is not None
    assert route_with_registry_async is not None

    run = None
    rl = None
    if getattr(settings, "runlog_enabled", True):
        try:
            rl = runlog or RunLogger(base_dir=str(getattr(settings, "runlog_dir", "data/runs") or "data/runs"))
            run = rl.start(intent=str(plan.intent or "react"))
            rl.append(
                run,
                "plan",
                {"intent": plan.intent, "risk": str(plan.risk), "tool_calls": [c.model_dump() for c in plan.tool_calls]},
            )
        except Exception:
            rl = None
            run = None

    max_steps = int(getattr(settings, "autonomy_max_steps", 12) or 12) if getattr(settings, "autonomy_enabled", False) else 6
    checkpoint_every = int(getattr(settings, "autonomy_checkpoint_every", 4) or 4)
    if checkpoint_every < 1:
        checkpoint_every = 1

    original_user_message = (plan.user_message or "").strip()
    current_plan = plan

    single_shot_tools = {"edu.pdf_word_autofill", "finance.crypto_market_chart"}
    trace_messages: list[dict[str, str]] = []

    for step in range(1, max_steps + 1):
        t_step = None
        try:
            if metrics is not None:
                metrics.inc("react.step")
                t_step = metrics.timer()
        except Exception:
            t_step = None
        state = ReactState.INIT_STEP
        call: ToolCall | None = None
        normalized_plan: Plan | None = None
        result = None

        while True:
            if state is ReactState.INIT_STEP:
                if not current_plan.tool_calls:
                    text = (current_plan.final_response or "").strip() or "Feito."
                    console.print(f"Agente> {text}")
                    memory.append("agent_response", {"text": text})
                    if rl is not None and run is not None:
                        try:
                            rl.append(run, "react_step", {"step": step, "state": "no_tools", "final": True})
                            if metrics is not None:
                                rl.append(run, "metrics", metrics.snapshot())
                        except Exception:
                            pass
                    return text

                call = current_plan.tool_calls[0]
                state = ReactState.PREFLIGHT
                continue

            if state is ReactState.PREFLIGHT:
                assert call is not None
                step_plan = current_plan.model_copy(update={"tool_calls": [call]})
                effective_risk = effective_risk_for_plan(step_plan, registry, settings=settings)
                effective_plan = step_plan if effective_risk == step_plan.risk else step_plan.model_copy(update={"risk": effective_risk})
                normalized_plan, _ = normalize_plan_args(effective_plan, settings=settings)

                preflight_error = preflight_validate_plan(normalized_plan, registry, settings=settings)
                if preflight_error:
                    console.print(f"[red]Preflight error:[/red] {preflight_error}")
                    console.print("Agente> Não executei por segurança.")
                    if rl is not None and run is not None:
                        try:
                            rl.append(run, "preflight_error", {"error": preflight_error, "step": step})
                        except Exception:
                            pass
                    return None

                if getattr(settings, "ui_show_react_steps", False):
                    assert normalized_plan is not None
                    console.print(
                        Panel.fit(
                            f"ReAct step {step}/{max_steps}\nTool: {call.tool_name}\nRisk: {normalized_plan.risk}",
                            title="Plano",
                        )
                    )

                state = ReactState.POLICY
                continue

            if state is ReactState.POLICY:
                assert call is not None
                assert normalized_plan is not None

                if getattr(settings, "policy_enabled", True):
                    try:
                        eng = policy
                        if eng is None:
                            eng = PolicyEngine(path=str(getattr(settings, "policy_path", "data/policy.json") or "data/policy.json"))
                            eng.load()
                        ok, decisions = eng.decide_plan([call], plan_risk=normalized_plan.risk)
                        if not ok:
                            denied = [d for d in decisions if not d.allowed]
                            reason = denied[0].reason if denied else "policy denied"
                            console.print(Panel.fit(f"Policy bloqueou a tool.\nMotivo: {reason}", title="Policy"))
                            memory.append("policy_denied", {"tool": call.tool_name, "reason": reason, "step": step})
                            if rl is not None and run is not None:
                                try:
                                    rl.append(run, "policy_denied", {"tool": call.tool_name, "reason": reason, "step": step})
                                except Exception:
                                    pass
                            return None
                    except Exception as exc:  # noqa: BLE001
                        memory.append("policy_error", {"error": str(exc), "step": step})

                state = ReactState.HITL
                continue

            if state is ReactState.HITL:
                assert normalized_plan is not None
                assert call is not None

                if not require_approval(
                    normalized_plan,
                    enabled=settings.hitl_enabled,
                    min_risk=settings.hitl_min_risk,
                    require_token=settings.hitl_require_token,
                    remember=remember,
                    approvals=approvals,
                ):
                    console.print("Agente> Ok, não vou executar isso.")
                    if rl is not None and run is not None:
                        try:
                            rl.append(run, "hitl_denied", {"tool": call.tool_name, "step": step})
                        except Exception:
                            pass
                    return None

                state = ReactState.SNAPSHOT
                continue

            if state is ReactState.SNAPSHOT:
                assert normalized_plan is not None
                assert call is not None

                if (
                    getattr(settings, "snapshots_enabled", True)
                    and getattr(settings, "snapshots_auto_before_high_risk", True)
                    and normalized_plan.risk in {RiskLevel.HIGH, RiskLevel.CRITICAL}
                ):
                    try:
                        mgr = snapshot_mgr
                        if mgr is None:
                            mgr = SnapshotManager(snapshots_dir=str(getattr(settings, "snapshots_dir", "data/snapshots") or "data/snapshots"))
                        info = mgr.create(label=f"react_{call.tool_name}"[:40])
                        memory.append("snapshot_created", {"snapshot_id": info.snapshot_id, "tool": call.tool_name, "step": step})
                        if rl is not None and run is not None:
                            try:
                                rl.append(run, "snapshot_created", {"snapshot_id": info.snapshot_id, "tool": call.tool_name, "step": step})
                            except Exception:
                                pass
                    except Exception:
                        pass

                state = ReactState.RUN_TOOL
                continue

            if state is ReactState.RUN_TOOL:
                assert call is not None

                result = await run_tool_with_retry_async(console, settings, registry, call, memory)
                if rl is not None and run is not None:
                    try:
                        rl.append(
                            run,
                            "tool_result",
                            {
                                "tool": call.tool_name,
                                "args": call.args,
                                "status": result.status,
                                "output": result.output,
                                "error": result.error,
                                "step": step,
                            },
                        )
                    except Exception:
                        pass

                if result.status == "error":
                    console.print(f"[red]Tool error:[/red] {call.tool_name}: {result.error}")

                if getattr(settings, "ui_show_tool_outputs", True) and result.output:
                    out = result.output.strip()
                    if len(out) > 2000:
                        out = out[:2000] + "\n... [truncado]"
                    console.print(Panel(out, title=f"Tool: {call.tool_name}"))

                state = ReactState.SHORTCIRCUIT
                continue

            if state is ReactState.SHORTCIRCUIT:
                assert call is not None
                assert result is not None

                if result.status == "ok" and call.tool_name in single_shot_tools and (current_plan.intent or "").strip() == call.tool_name:
                    text = (result.output or "").strip() or "Feito."
                    console.print(f"Agente> {text}")
                    memory.append("agent_response", {"text": text})
                    return text

                state = ReactState.TRACE_AND_CHECKPOINT
                continue

            if state is ReactState.TRACE_AND_CHECKPOINT:
                assert call is not None
                assert result is not None

                out_short = (result.output or "").strip()
                if len(out_short) > 1200:
                    out_short = out_short[:1200] + "\n... [truncado]"
                err_short = str(result.error or "").strip()
                if len(err_short) > 800:
                    err_short = err_short[:800] + "... [truncado]"

                trace = {"tool": call.tool_name, "args": call.args, "status": result.status, "output": out_short, "error": err_short}
                trace_messages.append({"role": "assistant", "content": "TOOL_RESULT " + json.dumps(trace, ensure_ascii=False)})
                if len(trace_messages) > 8:
                    trace_messages = trace_messages[-8:]

                if getattr(settings, "autonomy_enabled", False) and checkpoint_every and (step % checkpoint_every == 0) and step < max_steps:
                    memory.append(
                        "autonomy_checkpoint",
                        {"step": step, "max_steps": max_steps, "last_tool": call.tool_name, "last_status": result.status},
                    )
                    console.print(Panel.fit(f"Checkpoint: step {step}/{max_steps}\nÚltima tool: {call.tool_name} ({result.status})", title="Autonomia"))

                if len(current_plan.tool_calls) > 1:
                    trace_messages.append(
                        {"role": "assistant", "content": "HINT: o plano anterior continha mais tool_calls; replaine considerando o objetivo original."}
                    )
                    if len(trace_messages) > 8:
                        trace_messages = trace_messages[-8:]

                state = ReactState.REPLAN
                continue

            if state is ReactState.REPLAN:
                conv_ctx = build_router_context_messages(memory, current_user_message=original_user_message, limit_messages=8)
                replanning_ctx = conv_ctx + trace_messages
                if rl is not None and run is not None:
                    try:
                        rl.append(run, "react_replan", {"step": step, "mode": "llm"})
                    except Exception:
                        pass
                new_plan = await route_llm_async(
                    settings,
                    original_user_message,
                    context_messages=replanning_ctx,
                    registry=registry,
                    metrics=metrics,
                    runlog=rl,
                    run=run,
                )
                if new_plan is None:
                    safe_settings = replace(settings, router_mode="heuristic")
                    new_plan = await route_with_registry_async(
                        safe_settings,
                        original_user_message,
                        registry=registry,
                        context_messages=replanning_ctx,
                        metrics=metrics,
                        runlog=rl,
                        run=run,
                    )

                memory.append(
                    "plan",
                    {"intent": new_plan.intent, "risk": str(new_plan.risk), "tool_calls": [c.model_dump() for c in new_plan.tool_calls]},
                )
                current_plan = new_plan
                break

            raise RuntimeError(f"Unhandled ReAct state: {state}")

    console.print("Agente> Parei para não entrar em loop. Se quiser, descreva o que você viu/obteve e eu continuo.")
    memory.append("agent_response", {"text": "Parei para não entrar em loop. Se quiser, descreva o que você viu/obteve e eu continuo."})
    return "Parei para não entrar em loop. Se quiser, descreva o que você viu/obteve e eu continuo."
