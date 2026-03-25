from omniscia.core.heuristic_handlers import run_heuristic_handlers


def test_fear_greed_routes():
    plan = run_heuristic_handlers(user_message="medo e ganância", norm="medo e ganancia", context_messages=None)
    assert plan is not None
    assert plan.intent == "finance.fear_greed_index"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "finance.fear_greed_index"
    assert plan.tool_calls[0].args == {"limit": 1}


def test_iss_position_routes():
    plan = run_heuristic_handlers(user_message="onde está a iss", norm="onde esta a iss", context_messages=None)
    assert plan is not None
    assert plan.intent == "space.iss_position"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "space.iss_position"


def test_earthquake_routes_with_days_and_mag():
    plan = run_heuristic_handlers(
        user_message="terremotos 3 dias mag 5", norm="terremotos 3 dias mag 5", context_messages=None
    )
    assert plan is not None
    assert plan.intent == "science.earthquake_usgs"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "science.earthquake_usgs"
    assert plan.tool_calls[0].args["days"] == 3
    assert plan.tool_calls[0].args["min_magnitude"] == 5.0
    assert plan.tool_calls[0].args["limit"] == 10


def test_covid_routes_country_or_global():
    plan_br = run_heuristic_handlers(user_message="covid no brasil", norm="covid no brasil", context_messages=None)
    assert plan_br is not None
    assert plan_br.intent == "health.covid_stats"
    assert plan_br.tool_calls and plan_br.tool_calls[0].tool_name == "health.covid_stats"
    assert plan_br.tool_calls[0].args.get("country") == "brasil"

    plan_global = run_heuristic_handlers(user_message="covid global", norm="covid global", context_messages=None)
    assert plan_global is not None
    assert plan_global.intent == "health.covid_stats"
    assert plan_global.tool_calls and plan_global.tool_calls[0].tool_name == "health.covid_stats"
    assert plan_global.tool_calls[0].args == {}
