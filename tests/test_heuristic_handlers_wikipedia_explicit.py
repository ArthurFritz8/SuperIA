from omniscia.core.heuristic_handlers import run_heuristic_handlers


def _route(text: str):
    return run_heuristic_handlers(user_message=text, norm=text.lower(), context_messages=None)


def test_wikipedia_colon_syntax():
    plan = _route("wikipedia: Alan Turing")
    assert plan is not None
    assert plan.intent == "knowledge.wikipedia_summary"
    assert plan.tool_calls[0].tool_name == "knowledge.wikipedia_summary"
    assert plan.tool_calls[0].args.get("title") == "Alan Turing"


def test_wikipedia_search_phrase():
    plan = _route("pesquise na wikipedia sobre redes neurais")
    assert plan is not None
    assert plan.intent == "knowledge.wikipedia_summary"
    assert plan.tool_calls[0].args.get("title") == "redes neurais"
