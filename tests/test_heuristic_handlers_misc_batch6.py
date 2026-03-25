import pytest

from omniscia.core.heuristic_handlers import run_heuristic_handlers
from omniscia.core.types import RiskLevel


def _r(msg: str):
    plan = run_heuristic_handlers(user_message=msg, norm=msg.lower(), context_messages=None)
    assert plan is not None
    return plan


@pytest.mark.parametrize(
    "msg",
    [
        "discord status",
        "status do discord",
    ],
)
def test_discord_status(msg: str):
    p = _r(msg)
    assert p.intent == "status.discord"
    assert p.risk == RiskLevel.MEDIUM
    assert [c.tool_name for c in p.tool_calls] == ["status.discord"]


@pytest.mark.parametrize(
    "msg",
    [
        "ibge estados",
        "ibge ufs",
    ],
)
def test_ibge_states(msg: str):
    p = _r(msg)
    assert p.intent == "br.ibge_states"
    assert p.risk == RiskLevel.MEDIUM
    assert [c.tool_name for c in p.tool_calls] == ["br.ibge_states"]


def test_ibge_municipalities_by_uf():
    p = _r("ibge municipios: sp")
    assert p.intent == "br.ibge_municipalities_by_uf"
    assert p.risk == RiskLevel.MEDIUM
    assert [c.tool_name for c in p.tool_calls] == ["br.ibge_municipalities_by_uf"]
    assert p.tool_calls[0].args["uf"] == "SP"
    assert p.tool_calls[0].args["limit"] == 20
