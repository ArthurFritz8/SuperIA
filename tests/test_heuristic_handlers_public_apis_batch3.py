from omniscia.core.heuristic_handlers import run_heuristic_handlers


def test_hackernews_front_page_routes():
    plan = run_heuristic_handlers(user_message="hacker news top", norm="hacker news top", context_messages=None)
    assert plan is not None
    assert plan.intent == "news.hackernews_front_page"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "news.hackernews_front_page"
    assert plan.tool_calls[0].args == {"limit": 10}


def test_spacex_latest_launch_routes():
    plan = run_heuristic_handlers(
        user_message="spacex latest launch", norm="spacex latest launch", context_messages=None
    )
    assert plan is not None
    assert plan.intent == "space.spacex_latest_launch"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "space.spacex_latest_launch"
    assert plan.tool_calls[0].args == {}


def test_archive_search_routes():
    plan = run_heuristic_handlers(
        user_message="archive: python", norm="archive: python", context_messages=None
    )
    assert plan is not None
    assert plan.intent == "archive.archiveorg_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "archive.archiveorg_search"
    assert plan.tool_calls[0].args == {"query": "python", "limit": 5}


def test_tvmaze_search_routes():
    plan = run_heuristic_handlers(
        user_message="tvmaze: friends", norm="tvmaze: friends", context_messages=None
    )
    assert plan is not None
    assert plan.intent == "media.tvmaze_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "media.tvmaze_search"
    assert plan.tool_calls[0].args == {"query": "friends", "limit": 5}
