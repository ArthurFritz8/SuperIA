from omniscia.core.heuristic_handlers import run_heuristic_handlers


def _route(text: str):
    return run_heuristic_handlers(user_message=text, norm=text.lower(), context_messages=None)


def test_omega_on():
    plan = _route("ativa o modo omega")
    assert plan is not None
    assert plan.intent == "core.omega_on"
    assert plan.tool_calls == []


def test_omega_off():
    plan = _route("desativa omega")
    assert plan is not None
    assert plan.intent == "core.omega_off"


def test_voice_off():
    plan = _route("silenciar")
    assert plan is not None
    assert plan.intent == "core.voice_off"


def test_voice_on():
    plan = _route("liga a voz")
    assert plan is not None
    assert plan.intent == "core.voice_on"


def test_autonomy_on():
    plan = _route("habilitar autonomia")
    assert plan is not None
    assert plan.intent == "core.autonomy_on"


def test_autonomy_off():
    plan = _route("desligar autopilot")
    assert plan is not None
    assert plan.intent == "core.autonomy_off"
