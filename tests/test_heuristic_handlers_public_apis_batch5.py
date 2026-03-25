from omniscia.core.heuristic_handlers import run_heuristic_handlers


def test_itunes_search_routes():
    plan = run_heuristic_handlers(user_message="itunes: daft punk", norm="itunes: daft punk", context_messages=None)
    assert plan is not None
    assert plan.intent == "music.itunes_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "music.itunes_search"
    assert plan.tool_calls[0].args == {"query": "daft punk", "media": "music", "limit": 5}


def test_google_books_search_routes():
    plan = run_heuristic_handlers(
        user_message="google books: dune", norm="google books: dune", context_messages=None
    )
    assert plan is not None
    assert plan.intent == "books.googlebooks_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "books.googlebooks_search"
    assert plan.tool_calls[0].args == {"query": "dune", "limit": 5}


def test_datamuse_synonyms_routes():
    plan = run_heuristic_handlers(
        user_message="sinônimos de rápido", norm="sinônimos de rápido", context_messages=None
    )
    assert plan is not None
    assert plan.intent == "language.datamuse_related_words"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "language.datamuse_related_words"
    assert plan.tool_calls[0].args == {"query": "rápido", "relation": "rel_syn", "max_results": 10}


def test_datamuse_generic_routes():
    plan = run_heuristic_handlers(user_message="datamuse: latency", norm="datamuse: latency", context_messages=None)
    assert plan is not None
    assert plan.intent == "language.datamuse_related_words"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "language.datamuse_related_words"
    assert plan.tool_calls[0].args == {"query": "latency", "relation": "ml", "max_results": 10}
