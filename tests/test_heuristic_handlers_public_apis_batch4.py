import pytest

from omniscia.core.heuristic_handlers import run_heuristic_handlers


def _route(msg: str):
    return run_heuristic_handlers(user_message=msg, norm=msg.casefold().strip(), context_messages=None)


def test_mealdb_search():
    plan = _route("mealdb: carbonara")
    assert plan is not None
    assert plan.intent == "food.meal_search"
    assert plan.tool_calls[0].tool_name == "food.meal_search"
    assert plan.tool_calls[0].args == {"query": "carbonara", "limit": 5}


def test_universities_search_with_country():
    plan = _route("universities: mit | country: united states")
    assert plan is not None
    assert plan.intent == "edu.universities_search"
    assert plan.tool_calls[0].tool_name == "edu.universities_search"
    assert plan.tool_calls[0].args == {"name": "mit", "limit": 10, "country": "united states"}


def test_agify_with_cc():
    plan = _route("agify: maria cc: BR")
    assert plan is not None
    assert plan.intent == "people.agify_name"
    assert plan.tool_calls[0].tool_name == "people.agify_name"
    assert plan.tool_calls[0].args == {"name": "maria", "country_code": "BR"}


def test_genderize_no_cc():
    plan = _route("genderize: alex")
    assert plan is not None
    assert plan.intent == "people.genderize_name"
    assert plan.tool_calls[0].tool_name == "people.genderize_name"
    assert plan.tool_calls[0].args == {"name": "alex"}


def test_nationalize():
    plan = _route("nationalize: gabriel")
    assert plan is not None
    assert plan.intent == "people.nationalize_name"
    assert plan.tool_calls[0].tool_name == "people.nationalize_name"
    assert plan.tool_calls[0].args == {"name": "gabriel", "limit": 5}


def test_dog_image():
    plan = _route("quero uma imagem de cachorro")
    assert plan is not None
    assert plan.intent == "fun.dog_image"
    assert plan.tool_calls[0].tool_name == "fun.dog_image"
    assert plan.tool_calls[0].args == {}


def test_jikan_anime_search():
    plan = _route("anime: naruto")
    assert plan is not None
    assert plan.intent == "anime.jikan_search"
    assert plan.tool_calls[0].tool_name == "anime.jikan_search"
    assert plan.tool_calls[0].args == {"query": "naruto", "limit": 5}


def test_met_object():
    plan = _route("met object: 123")
    assert plan is not None
    assert plan.intent == "art.met_object"
    assert plan.tool_calls[0].tool_name == "art.met_object"
    assert plan.tool_calls[0].args == {"object_id": 123}


def test_met_search():
    plan = _route("met museum: van gogh")
    assert plan is not None
    assert plan.intent == "art.met_search"
    assert plan.tool_calls[0].tool_name == "art.met_search"
    assert plan.tool_calls[0].args == {"query": "van gogh", "limit": 5}


def test_xkcd_num():
    plan = _route("xkcd: 42")
    assert plan is not None
    assert plan.intent == "fun.xkcd_comic"
    assert plan.tool_calls[0].tool_name == "fun.xkcd_comic"
    assert plan.tool_calls[0].args == {"num": 42}


@pytest.mark.parametrize("msg", ["xkcd", "xkcd latest", "xkcd último", "xkcd recente"])
def test_xkcd_latest(msg: str):
    plan = _route(msg)
    assert plan is not None
    assert plan.intent == "fun.xkcd_latest"
    assert plan.tool_calls[0].tool_name == "fun.xkcd_latest"
    assert plan.tool_calls[0].args == {}
