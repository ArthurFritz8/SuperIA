from omniscia.core.heuristic_handlers import run_heuristic_handlers


def test_openalex_routes():
    plan = run_heuristic_handlers(user_message="openalex: transformers", norm="openalex: transformers", context_messages=None)
    assert plan is not None
    assert plan.intent == "knowledge.openalex_works_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "knowledge.openalex_works_search"
    assert plan.tool_calls[0].args["max_results"] == 5
    assert plan.tool_calls[0].args["query"] == "transformers"


def test_wikidata_entity_routes():
    plan = run_heuristic_handlers(user_message="wikidata id: Q42", norm="wikidata id: q42", context_messages=None)
    assert plan is not None
    assert plan.intent == "knowledge.wikidata_entity"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "knowledge.wikidata_entity"
    assert plan.tool_calls[0].args == {"id": "Q42"}


def test_wikidata_search_routes():
    plan = run_heuristic_handlers(user_message="wikidata: alan turing", norm="wikidata: alan turing", context_messages=None)
    assert plan is not None
    assert plan.intent == "knowledge.wikidata_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "knowledge.wikidata_search"
    assert plan.tool_calls[0].args["lang"] == "pt"
    assert plan.tool_calls[0].args["limit"] == 5
    assert plan.tool_calls[0].args["query"] == "alan turing"


def test_worldbank_indicator_routes():
    plan = run_heuristic_handlers(
        user_message="worldbank: BR SP.POP.TOTL 2010:2024",
        norm="worldbank: br sp.pop.totl 2010:2024",
        context_messages=None,
    )
    assert plan is not None
    assert plan.intent == "data.worldbank_indicator"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "data.worldbank_indicator"
    assert plan.tool_calls[0].args["country_code"] == "BR"
    assert plan.tool_calls[0].args["indicator"] == "SP.POP.TOTL"
    assert plan.tool_calls[0].args["date"] == "2010:2024"
