from omniscia.core.heuristic_handlers import run_heuristic_handlers


def _route(text: str):
    return run_heuristic_handlers(user_message=text, norm=text.lower(), context_messages=None)


def test_geo_onde_fica():
    plan = _route("onde fica MASP?")
    assert plan is not None
    assert plan.intent == "geo.geocode"
    assert plan.tool_calls[0].tool_name == "geo.geocode"


def test_geo_geocode_explicit():
    plan = _route("geocode: av paulista, sp")
    assert plan is not None
    assert plan.intent == "geo.geocode"


def test_geo_reverse_geocode():
    plan = _route("endereço de -23.55, -46.63")
    assert plan is not None
    assert plan.intent == "geo.reverse_geocode"
    assert plan.tool_calls[0].tool_name == "geo.reverse_geocode"


def test_geo_route():
    plan = _route("rota de Campinas para São Paulo")
    assert plan is not None
    assert plan.intent == "geo.route_osrm"
    assert plan.tool_calls[0].tool_name == "geo.route_osrm"
