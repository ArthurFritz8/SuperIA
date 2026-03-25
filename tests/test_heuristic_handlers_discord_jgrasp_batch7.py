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
        "abre o discord",
        "abrir discord",
        "open discord",
    ],
)
def test_discord_open(msg: str):
    p = _r(msg)
    assert p.intent == "os.open_app"
    assert p.risk == RiskLevel.MEDIUM
    assert [c.tool_name for c in p.tool_calls] == ["os.open_app"]
    assert p.tool_calls[0].args.get("app") == "discord"


@pytest.mark.parametrize(
    "msg,visible_only",
    [
        ("feche o discord", True),
        ("feche o discord no segundo plano", False),
    ],
)
def test_discord_close(msg: str, visible_only: bool):
    p = _r(msg)
    assert p.intent == "os.close_app"
    assert p.risk == RiskLevel.HIGH
    assert [c.tool_name for c in p.tool_calls] == ["os.close_app"]
    assert p.tool_calls[0].args.get("app") == "discord"
    assert p.tool_calls[0].args.get("visible_only") is visible_only


def test_discord_send_message_explicit():
    p = _r('mandar mensagem para Alice no discord: oi')
    assert p.intent == "discord.send_message"
    assert p.risk == RiskLevel.CRITICAL
    assert [c.tool_name for c in p.tool_calls] == ["os.open_app", "discord.send_message"]
    assert p.tool_calls[1].args.get("to") == "Alice"
    assert p.tool_calls[1].args.get("message") == "oi"


def test_discord_send_message_click_chat_phrase_normalizes_oi():
    p = _r("clique no chat da Alice e mande um oi para ela")
    assert p.intent == "discord.send_message"
    assert p.risk == RiskLevel.CRITICAL
    assert [c.tool_name for c in p.tool_calls] == ["os.open_app", "discord.send_message"]
    assert p.tool_calls[1].args.get("to") == "Alice"
    assert p.tool_calls[1].args.get("message") == "oi"


def test_jgrasp_hello_world_defaults_to_scratch():
    p = _r("quero que voce crie um programa simples (hello world) no jgrasp")
    assert p.intent == "jgrasp.create_java_program"
    assert p.risk == RiskLevel.HIGH
    assert [c.tool_name for c in p.tool_calls] == ["os.open_app", "jgrasp.create_java_program"]
    assert str(p.tool_calls[1].args.get("path")) == "scratch/HelloWorld.java"


def test_jgrasp_hello_world_desktop_prefix_when_requested():
    p = _r("crie um programa simples no jgrasp e salve na area de trabalho")
    assert p.intent == "jgrasp.create_java_program"
    assert p.risk == RiskLevel.HIGH
    assert [c.tool_name for c in p.tool_calls] == ["os.open_app", "jgrasp.create_java_program"]
    assert str(p.tool_calls[1].args.get("path")) == "desktop:/MeuProjeto/MeuProjeto.java"
