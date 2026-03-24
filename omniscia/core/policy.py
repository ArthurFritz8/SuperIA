"""Policy engine (guardrails beyond HITL).

Goals:
- Allow/deny tool calls based on a local, auditable policy file.
- Block unsafe actions *before* prompting HITL (so user isn't spammed).
- Keep defaults non-breaking: when policy is missing/invalid, fall back to allow.

Design:
- Policy is local JSON at `data/policy.json` by default.
- Matching supports:
  - exact tool name
  - prefix match via trailing '*'
  - regex via 're:<pattern>'

This module is offline and does not use LLM.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from omniscia.core.types import RiskLevel, ToolCall


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str
    rule: str | None = None


@dataclass(frozen=True)
class Policy:
    enabled: bool
    default_action: str  # 'allow' | 'deny'
    allow: tuple[str, ...]
    deny: tuple[str, ...]
    deny_risk_at_or_above: RiskLevel | None
    # Optional: restrict file-like args to these roots (workspace-relative prefixes)
    allowed_path_prefixes: tuple[str, ...]

    @staticmethod
    def default() -> "Policy":
        return Policy(
            enabled=True,
            default_action="allow",
            allow=(),
            deny=(),
            deny_risk_at_or_above=None,
            allowed_path_prefixes=(),
        )


def _norm_prefix(p: str) -> str:
    t = (p or "").strip().replace("\\", "/")
    while t.startswith("./"):
        t = t[2:]
    return t


def _match(pattern: str, tool_name: str) -> bool:
    p = (pattern or "").strip()
    t = (tool_name or "").strip()
    if not p or not t:
        return False

    if p.startswith("re:"):
        try:
            return bool(re.search(p[3:], t))
        except re.error:
            return False

    if p.endswith("*"):
        return t.startswith(p[:-1])

    return t == p


def _risk_rank(risk: RiskLevel) -> int:
    order = {
        RiskLevel.LOW: 0,
        RiskLevel.MEDIUM: 1,
        RiskLevel.HIGH: 2,
        RiskLevel.CRITICAL: 3,
    }
    return order.get(risk, 3)


def _extract_paths(args: dict[str, Any]) -> list[str]:
    # Best-effort: common arg keys used across tools.
    keys = ("path", "paths", "src", "dst", "out_path")
    found: list[str] = []
    for k in keys:
        v = args.get(k)
        if isinstance(v, str) and v.strip():
            found.append(v.strip())
        elif isinstance(v, list):
            for it in v:
                if isinstance(it, str) and it.strip():
                    found.append(it.strip())
    return found


class PolicyEngine:
    def __init__(self, *, path: str = "data/policy.json") -> None:
        self.path = Path(path)
        self.policy = Policy.default()
        self._load_error: str | None = None

    @property
    def load_error(self) -> str | None:
        return self._load_error

    def load(self) -> None:
        self._load_error = None
        try:
            if not self.path.exists():
                self.policy = Policy.default()
                return
            raw = self.path.read_text(encoding="utf-8", errors="replace").strip()
            if not raw:
                self.policy = Policy.default()
                return
            obj = json.loads(raw)
            if not isinstance(obj, dict):
                self.policy = Policy.default()
                self._load_error = "policy JSON não é um objeto"
                return

            enabled = bool(obj.get("enabled", True))
            default_action = str(obj.get("default_action", "allow") or "allow").strip().lower()
            if default_action not in {"allow", "deny"}:
                default_action = "allow"

            allow = obj.get("allow")
            deny = obj.get("deny")
            allow_list = tuple(str(x).strip() for x in (allow or []) if isinstance(x, (str, int, float)) and str(x).strip()) if isinstance(allow, list) else ()
            deny_list = tuple(str(x).strip() for x in (deny or []) if isinstance(x, (str, int, float)) and str(x).strip()) if isinstance(deny, list) else ()

            deny_risk_raw = obj.get("deny_risk_at_or_above")
            deny_risk = None
            if isinstance(deny_risk_raw, str) and deny_risk_raw.strip():
                try:
                    deny_risk = RiskLevel(deny_risk_raw.strip().upper())
                except Exception:
                    deny_risk = None

            allowed_prefixes_raw = obj.get("allowed_path_prefixes")
            allowed_prefixes = ()
            if isinstance(allowed_prefixes_raw, list):
                allowed_prefixes = tuple(_norm_prefix(str(x)) for x in allowed_prefixes_raw if str(x).strip())

            self.policy = Policy(
                enabled=enabled,
                default_action=default_action,
                allow=allow_list,
                deny=deny_list,
                deny_risk_at_or_above=deny_risk,
                allowed_path_prefixes=allowed_prefixes,
            )
        except Exception as exc:  # noqa: BLE001
            self.policy = Policy.default()
            self._load_error = f"{type(exc).__name__}: {exc}"

    def save(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.load()

    def decide_call(self, call: ToolCall, *, plan_risk: RiskLevel | None = None) -> PolicyDecision:
        p = self.policy
        if not p.enabled:
            return PolicyDecision(True, "policy disabled")

        tool = (call.tool_name or "").strip()
        if not tool:
            return PolicyDecision(False, "tool_name vazio", rule="invalid")

        if plan_risk is not None and p.deny_risk_at_or_above is not None:
            if _risk_rank(plan_risk) >= _risk_rank(p.deny_risk_at_or_above):
                return PolicyDecision(False, f"risk {plan_risk} bloqueado por policy", rule="deny_risk_at_or_above")

        # Explicit deny wins unless explicitly allowed.
        for rule in p.allow:
            if _match(rule, tool):
                return PolicyDecision(True, "explicit allow", rule=rule)

        for rule in p.deny:
            if _match(rule, tool):
                return PolicyDecision(False, "explicit deny", rule=rule)

        # Path restrictions (best-effort)
        if p.allowed_path_prefixes:
            paths = _extract_paths(call.args or {})
            for raw in paths:
                rp = _norm_prefix(raw)
                # Ignore known-folder prefixes (desktop:/ etc)
                if re.match(r"^[a-zA-Z]+:/", rp):
                    continue
                if rp.startswith("/") or ":" in rp:
                    return PolicyDecision(False, f"path absoluto não permitido: {raw}", rule="allowed_path_prefixes")
                if not any(rp.startswith(pref) for pref in p.allowed_path_prefixes):
                    return PolicyDecision(False, f"path fora do allowlist: {raw}", rule="allowed_path_prefixes")

        # Default action
        if p.default_action == "deny":
            return PolicyDecision(False, "default deny", rule="default_action")
        return PolicyDecision(True, "default allow", rule="default_action")

    def decide_plan(self, calls: Iterable[ToolCall], *, plan_risk: RiskLevel | None = None) -> tuple[bool, list[PolicyDecision]]:
        decisions: list[PolicyDecision] = []
        ok = True
        for c in calls:
            d = self.decide_call(c, plan_risk=plan_risk)
            decisions.append(d)
            if not d.allowed:
                ok = False
        return ok, decisions
