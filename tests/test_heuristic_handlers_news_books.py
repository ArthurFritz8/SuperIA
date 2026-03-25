from omniscia.core.heuristic_handlers import run_heuristic_handlers


def _route(text: str):
    return run_heuristic_handlers(user_message=text, norm=text.lower(), context_messages=None)


def test_news_gdelt():
    plan = _route("notícias sobre IA")
    assert plan is not None
    assert plan.intent == "news.gdelt_search"
    assert plan.tool_calls[0].tool_name == "news.gdelt_search"


def test_books_openlibrary():
    plan = _route("livro: clean code")
    assert plan is not None
    assert plan.intent == "books.openlibrary_search"
    assert plan.tool_calls[0].tool_name == "books.openlibrary_search"


def test_hacker_news_not_routed_to_gdelt():
    plan = _route("hacker news: ai")
    assert plan is None
