from __future__ import annotations

from omniscia.core.config import Settings
from omniscia.core.router import route
from omniscia.core.types import RiskLevel


def test_geo_geocode_route():
    settings = Settings.load()
    plan = route(settings, "coordenadas de São Paulo")
    assert plan.intent == "geo.geocode"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "geo.geocode"
    assert plan.risk == RiskLevel.MEDIUM


def test_geo_reverse_geocode_route():
    settings = Settings.load()
    plan = route(settings, "endereço de -23.55, -46.63")
    assert plan.intent == "geo.reverse_geocode"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "geo.reverse_geocode"
    assert plan.risk == RiskLevel.MEDIUM


def test_geo_route_osrm_route():
    settings = Settings.load()
    plan = route(settings, "rota de Campinas para São Paulo")
    assert plan.intent == "geo.route_osrm"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "geo.route_osrm"
    assert plan.risk == RiskLevel.MEDIUM


def test_fx_convert_route():
    settings = Settings.load()
    plan = route(settings, "converter 10 usd para brl")
    assert plan.intent == "finance.fx_convert"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "finance.fx_convert"
    assert plan.risk == RiskLevel.MEDIUM


def test_country_info_route():
    settings = Settings.load()
    plan = route(settings, "país: Brasil")
    assert plan.intent == "data.country_info"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "data.country_info"
    assert plan.risk == RiskLevel.MEDIUM


def test_world_time_route():
    settings = Settings.load()
    plan = route(settings, "hora em America/Sao_Paulo")
    assert plan.intent == "time.world_time"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "time.world_time"
    assert plan.risk == RiskLevel.MEDIUM


def test_news_gdelt_route():
    settings = Settings.load()
    plan = route(settings, "notícias sobre inteligência artificial")
    assert plan.intent == "news.gdelt_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "news.gdelt_search"
    assert plan.risk == RiskLevel.MEDIUM


def test_books_openlibrary_route():
    settings = Settings.load()
    plan = route(settings, "livro: Clean Code")
    assert plan.intent == "books.openlibrary_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "books.openlibrary_search"
    assert plan.risk == RiskLevel.MEDIUM


def test_holidays_route():
    settings = Settings.load()
    plan = route(settings, "feriados 2026 BR")
    assert plan.intent == "calendar.holidays"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "calendar.holidays"
    assert plan.risk == RiskLevel.MEDIUM


def test_crossref_route():
    settings = Settings.load()
    plan = route(settings, "crossref: attention is all you need")
    assert plan.intent == "papers.crossref_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "papers.crossref_search"
    assert plan.risk == RiskLevel.MEDIUM


def test_fear_greed_route():
    settings = Settings.load()
    plan = route(settings, "fear and greed")
    assert plan.intent == "finance.fear_greed_index"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "finance.fear_greed_index"
    assert plan.risk == RiskLevel.MEDIUM


def test_iss_route():
    settings = Settings.load()
    plan = route(settings, "onde está a ISS agora?")
    assert plan.intent == "space.iss_position"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "space.iss_position"
    assert plan.risk == RiskLevel.MEDIUM


def test_earthquake_route():
    settings = Settings.load()
    plan = route(settings, "terremotos magnitude 5 últimos 7 dias")
    assert plan.intent == "science.earthquake_usgs"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "science.earthquake_usgs"
    assert plan.risk == RiskLevel.MEDIUM


def test_covid_route_country():
    settings = Settings.load()
    plan = route(settings, "covid no Brasil")
    assert plan.intent == "health.covid_stats"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "health.covid_stats"
    assert plan.risk == RiskLevel.MEDIUM


def test_openalex_route():
    settings = Settings.load()
    plan = route(settings, "openalex: diffusion models")
    assert plan.intent == "knowledge.openalex_works_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "knowledge.openalex_works_search"
    assert plan.risk == RiskLevel.MEDIUM


def test_wikidata_route():
    settings = Settings.load()
    plan = route(settings, "wikidata: Alan Turing")
    assert plan.intent == "knowledge.wikidata_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "knowledge.wikidata_search"
    assert plan.risk == RiskLevel.MEDIUM


def test_wikidata_entity_route():
    settings = Settings.load()
    plan = route(settings, "wikidata id: Q42")
    assert plan.intent == "knowledge.wikidata_entity"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "knowledge.wikidata_entity"
    assert plan.risk == RiskLevel.MEDIUM


def test_wikidata_entity_route_entity_keyword_case_insensitive():
    settings = Settings.load()
    plan = route(settings, "entity: q42")
    assert plan.intent == "knowledge.wikidata_entity"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "knowledge.wikidata_entity"
    assert plan.risk == RiskLevel.MEDIUM


def test_wikidata_entity_route_without_colon():
    settings = Settings.load()
    plan = route(settings, "wikidata id Q42")
    assert plan.intent == "knowledge.wikidata_entity"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "knowledge.wikidata_entity"
    assert plan.risk == RiskLevel.MEDIUM


def test_wikidata_entity_route_with_extra_text():
    settings = Settings.load()
    plan = route(settings, "por favor, wikidata id: q42 agora")
    assert plan.intent == "knowledge.wikidata_entity"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "knowledge.wikidata_entity"
    assert plan.risk == RiskLevel.MEDIUM


def test_worldbank_route():
    settings = Settings.load()
    plan = route(settings, "worldbank: BR SP.POP.TOTL")
    assert plan.intent == "data.worldbank_indicator"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "data.worldbank_indicator"
    assert plan.risk == RiskLevel.MEDIUM


def test_hackernews_front_page_route():
    settings = Settings.load()
    plan = route(settings, "hacker news top")
    assert plan.intent == "news.hackernews_front_page"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "news.hackernews_front_page"
    assert plan.risk == RiskLevel.MEDIUM


def test_github_repo_search_route():
    settings = Settings.load()
    plan = route(settings, "github: typer rich")
    assert plan.intent == "code.github_repo_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "code.github_repo_search"
    assert plan.risk == RiskLevel.MEDIUM


def test_stackexchange_search_route():
    settings = Settings.load()
    plan = route(settings, "stackoverflow: list index out of range")
    assert plan.intent == "qa.stackexchange_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "qa.stackexchange_search"
    assert plan.risk == RiskLevel.MEDIUM


def test_dictionary_define_route():
    settings = Settings.load()
    plan = route(settings, "defina recursion")
    assert plan.intent == "language.dictionary_define"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "language.dictionary_define"
    assert plan.risk == RiskLevel.MEDIUM


def test_lyrics_route():
    settings = Settings.load()
    plan = route(settings, "letra: Queen - Bohemian Rhapsody")
    assert plan.intent == "media.lyrics"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "media.lyrics"
    assert plan.risk == RiskLevel.MEDIUM


def test_joke_route():
    settings = Settings.load()
    plan = route(settings, "me conte uma piada")
    assert plan.intent == "fun.joke"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "fun.joke"
    assert plan.risk == RiskLevel.MEDIUM


def test_trivia_route():
    settings = Settings.load()
    plan = route(settings, "trivia")
    assert plan.intent == "fun.trivia"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "fun.trivia"
    assert plan.risk == RiskLevel.MEDIUM


def test_pokemon_route():
    settings = Settings.load()
    plan = route(settings, "pokemon: pikachu")
    assert plan.intent == "fun.pokemon_info"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "fun.pokemon_info"
    assert plan.risk == RiskLevel.MEDIUM


def test_ip_info_route_my_ip():
    settings = Settings.load()
    plan = route(settings, "meu ip")
    assert plan.intent == "net.ip_info"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "net.ip_info"
    assert plan.risk == RiskLevel.MEDIUM


def test_random_user_route():
    settings = Settings.load()
    plan = route(settings, "pessoa aleatória")
    assert plan.intent == "people.random_user"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "people.random_user"
    assert plan.risk == RiskLevel.MEDIUM


def test_cat_fact_route():
    settings = Settings.load()
    plan = route(settings, "cat fact")
    assert plan.intent == "fun.cat_fact"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "fun.cat_fact"
    assert plan.risk == RiskLevel.MEDIUM


def test_qr_code_url_route():
    settings = Settings.load()
    plan = route(settings, "qr: https://example.com")
    assert plan.intent == "utils.qr_code_url"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "utils.qr_code_url"
    assert plan.risk == RiskLevel.MEDIUM


def test_osv_vuln_route_cve():
    settings = Settings.load()
    plan = route(settings, "CVE-2024-1234")
    assert plan.intent == "sec.osv_vuln"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "sec.osv_vuln"
    assert plan.risk == RiskLevel.MEDIUM


def test_osv_query_route_package_version():
    settings = Settings.load()
    plan = route(settings, "osv: PyPI jinja2 3.1.4")
    assert plan.intent == "sec.osv_query"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "sec.osv_query"
    assert plan.risk == RiskLevel.MEDIUM


def test_pypi_project_route():
    settings = Settings.load()
    plan = route(settings, "pypi: requests")
    assert plan.intent == "pkg.pypi_project"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "pkg.pypi_project"
    assert plan.risk == RiskLevel.MEDIUM


def test_npm_package_route():
    settings = Settings.load()
    plan = route(settings, "npm: express")
    assert plan.intent == "pkg.npm_package"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "pkg.npm_package"
    assert plan.risk == RiskLevel.MEDIUM


def test_cratesio_crate_route():
    settings = Settings.load()
    plan = route(settings, "crates: tokio")
    assert plan.intent == "pkg.cratesio_crate"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "pkg.cratesio_crate"
    assert plan.risk == RiskLevel.MEDIUM


def test_dns_resolve_route():
    settings = Settings.load()
    plan = route(settings, "dns: example.com A")
    assert plan.intent == "net.dns_google_resolve"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "net.dns_google_resolve"
    assert plan.risk == RiskLevel.MEDIUM


def test_github_status_route():
    settings = Settings.load()
    plan = route(settings, "github status")
    assert plan.intent == "status.github"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "status.github"
    assert plan.risk == RiskLevel.MEDIUM


def test_cloudflare_status_route():
    settings = Settings.load()
    plan = route(settings, "cloudflare status")
    assert plan.intent == "status.cloudflare"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "status.cloudflare"
    assert plan.risk == RiskLevel.MEDIUM


def test_discord_status_route():
    settings = Settings.load()
    plan = route(settings, "discord status")
    assert plan.intent == "status.discord"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "status.discord"
    assert plan.risk == RiskLevel.MEDIUM


def test_rdap_domain_route():
    settings = Settings.load()
    plan = route(settings, "whois: example.com")
    assert plan.intent == "net.rdap_domain"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "net.rdap_domain"
    assert plan.risk == RiskLevel.MEDIUM


def test_rdap_ip_route():
    settings = Settings.load()
    plan = route(settings, "rdap ip: 8.8.8.8")
    assert plan.intent == "net.rdap_ip"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "net.rdap_ip"
    assert plan.risk == RiskLevel.MEDIUM


def test_bgpview_ip_route():
    settings = Settings.load()
    plan = route(settings, "bgp ip: 8.8.8.8")
    assert plan.intent == "net.bgpview_ip"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "net.bgpview_ip"
    assert plan.risk == RiskLevel.MEDIUM


def test_bgpview_asn_route():
    settings = Settings.load()
    plan = route(settings, "asn: 15169")
    assert plan.intent == "net.bgpview_asn"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "net.bgpview_asn"
    assert plan.risk == RiskLevel.MEDIUM


def test_crtsh_route():
    settings = Settings.load()
    plan = route(settings, "crtsh: example.com")
    assert plan.intent == "sec.crtsh_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "sec.crtsh_search"
    assert plan.risk == RiskLevel.MEDIUM


def test_cisa_kev_route():
    settings = Settings.load()
    plan = route(settings, "kev: CVE-2021-44228")
    assert plan.intent == "sec.cisa_kev_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "sec.cisa_kev_search"
    assert plan.risk == RiskLevel.MEDIUM


def test_npm_status_route():
    settings = Settings.load()
    plan = route(settings, "npm status")
    assert plan.intent == "status.npm"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "status.npm"
    assert plan.risk == RiskLevel.MEDIUM


def test_openai_status_route():
    settings = Settings.load()
    plan = route(settings, "openai status")
    assert plan.intent == "status.openai"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "status.openai"
    assert plan.risk == RiskLevel.MEDIUM


def test_ripestat_ip_route():
    settings = Settings.load()
    plan = route(settings, "ripestat ip: 8.8.8.8")
    assert plan.intent == "net.ripestat_ip"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "net.ripestat_ip"
    assert plan.risk == RiskLevel.MEDIUM


def test_ripestat_asn_route():
    settings = Settings.load()
    plan = route(settings, "ripe stat asn: 15169")
    assert plan.intent == "net.ripestat_asn"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "net.ripestat_asn"
    assert plan.risk == RiskLevel.MEDIUM


def test_peeringdb_asn_route():
    settings = Settings.load()
    plan = route(settings, "peeringdb asn: 15169")
    assert plan.intent == "net.peeringdb_asn"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "net.peeringdb_asn"
    assert plan.risk == RiskLevel.MEDIUM


def test_urlhaus_url_route():
    settings = Settings.load()
    plan = route(settings, "urlhaus url: http://example.com/bad")
    assert plan.intent == "sec.urlhaus_url"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "sec.urlhaus_url"
    assert plan.risk == RiskLevel.MEDIUM


def test_urlhaus_host_route():
    settings = Settings.load()
    plan = route(settings, "urlhaus host: example.com")
    assert plan.intent == "sec.urlhaus_host"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "sec.urlhaus_host"
    assert plan.risk == RiskLevel.MEDIUM


def test_threatfox_ioc_route():
    settings = Settings.load()
    plan = route(settings, "threatfox: 1.2.3.4")
    assert plan.intent == "sec.threatfox_ioc_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "sec.threatfox_ioc_search"
    assert plan.risk == RiskLevel.MEDIUM


def test_docker_status_route():
    settings = Settings.load()
    plan = route(settings, "docker status")
    assert plan.intent == "status.docker"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "status.docker"
    assert plan.risk == RiskLevel.MEDIUM


def test_atlassian_status_route():
    settings = Settings.load()
    plan = route(settings, "atlassian status")
    assert plan.intent == "status.atlassian"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "status.atlassian"
    assert plan.risk == RiskLevel.MEDIUM


def test_zoom_status_route():
    settings = Settings.load()
    plan = route(settings, "zoom status")
    assert plan.intent == "status.zoom"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "status.zoom"
    assert plan.risk == RiskLevel.MEDIUM


def test_feodotracker_route():
    settings = Settings.load()
    plan = route(settings, "feodo tracker")
    assert plan.intent == "sec.feodotracker_ip_blocklist"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "sec.feodotracker_ip_blocklist"
    assert plan.risk == RiskLevel.MEDIUM


def test_hashlookup_route():
    settings = Settings.load()
    plan = route(settings, "hashlookup sha256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
    assert plan.intent == "sec.hashlookup"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "sec.hashlookup"
    assert plan.risk == RiskLevel.MEDIUM


def test_gitlab_status_route():
    settings = Settings.load()
    plan = route(settings, "gitlab status")
    assert plan.intent == "status.gitlab"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "status.gitlab"
    assert plan.risk == RiskLevel.MEDIUM


def test_spacex_latest_launch_route():
    settings = Settings.load()
    plan = route(settings, "spacex último lançamento")
    assert plan.intent == "space.spacex_latest_launch"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "space.spacex_latest_launch"
    assert plan.risk == RiskLevel.MEDIUM


def test_archiveorg_search_route():
    settings = Settings.load()
    plan = route(settings, "archive: alan turing")
    assert plan.intent == "archive.archiveorg_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "archive.archiveorg_search"
    assert plan.risk == RiskLevel.MEDIUM


def test_tvmaze_search_route():
    settings = Settings.load()
    plan = route(settings, "tvmaze: friends")
    assert plan.intent == "media.tvmaze_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "media.tvmaze_search"
    assert plan.risk == RiskLevel.MEDIUM


def test_mealdb_search_route():
    settings = Settings.load()
    plan = route(settings, "mealdb: arrabiata")
    assert plan.intent == "food.meal_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "food.meal_search"
    assert plan.risk == RiskLevel.MEDIUM


def test_universities_search_route():
    settings = Settings.load()
    plan = route(settings, "universidades: usp | país: Brasil")
    assert plan.intent == "edu.universities_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "edu.universities_search"
    assert plan.risk == RiskLevel.MEDIUM


def test_agify_route():
    settings = Settings.load()
    plan = route(settings, "agify: maria cc: br")
    assert plan.intent == "people.agify_name"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "people.agify_name"
    assert plan.risk == RiskLevel.MEDIUM


def test_genderize_route():
    settings = Settings.load()
    plan = route(settings, "genderize: maria cc: br")
    assert plan.intent == "people.genderize_name"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "people.genderize_name"
    assert plan.risk == RiskLevel.MEDIUM


def test_nationalize_route():
    settings = Settings.load()
    plan = route(settings, "nationalize: maria")
    assert plan.intent == "people.nationalize_name"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "people.nationalize_name"
    assert plan.risk == RiskLevel.MEDIUM


def test_dog_image_route():
    settings = Settings.load()
    plan = route(settings, "cachorro imagem")
    assert plan.intent == "fun.dog_image"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "fun.dog_image"
    assert plan.risk == RiskLevel.MEDIUM


def test_jikan_anime_search_route():
    settings = Settings.load()
    plan = route(settings, "anime: naruto")
    assert plan.intent == "anime.jikan_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "anime.jikan_search"
    assert plan.risk == RiskLevel.MEDIUM


def test_met_search_route():
    settings = Settings.load()
    plan = route(settings, "met: sunflowers")
    assert plan.intent == "art.met_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "art.met_search"
    assert plan.risk == RiskLevel.MEDIUM


def test_met_object_route():
    settings = Settings.load()
    plan = route(settings, "met object: 436535")
    assert plan.intent == "art.met_object"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "art.met_object"
    assert plan.risk == RiskLevel.MEDIUM


def test_artic_search_route():
    settings = Settings.load()
    plan = route(settings, "artic: monet")
    assert plan.intent == "art.artic_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "art.artic_search"
    assert plan.risk == RiskLevel.MEDIUM


def test_chess_player_route():
    settings = Settings.load()
    plan = route(settings, "chess: hikaru")
    assert plan.intent == "chess.chesscom_player"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "chess.chesscom_player"
    assert plan.risk == RiskLevel.MEDIUM


def test_chess_stats_route():
    settings = Settings.load()
    plan = route(settings, "chess stats: hikaru")
    assert plan.intent == "chess.chesscom_stats"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "chess.chesscom_stats"
    assert plan.risk == RiskLevel.MEDIUM


def test_chess_daily_puzzle_route():
    settings = Settings.load()
    plan = route(settings, "chess puzzle")
    assert plan.intent == "chess.chesscom_daily_puzzle"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "chess.chesscom_daily_puzzle"
    assert plan.risk == RiskLevel.MEDIUM


def test_openbrewerydb_search_route():
    settings = Settings.load()
    plan = route(settings, "cervejarias: rio")
    assert plan.intent == "drink.openbrewerydb_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "drink.openbrewerydb_search"
    assert plan.risk == RiskLevel.MEDIUM


def test_deck_draw_route():
    settings = Settings.load()
    plan = route(settings, "cartas: 3")
    assert plan.intent == "fun.deck_draw"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "fun.deck_draw"
    assert plan.risk == RiskLevel.MEDIUM


def test_xkcd_latest_route():
    settings = Settings.load()
    plan = route(settings, "xkcd")
    assert plan.intent == "fun.xkcd_latest"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "fun.xkcd_latest"
    assert plan.risk == RiskLevel.MEDIUM


def test_xkcd_comic_route():
    settings = Settings.load()
    plan = route(settings, "xkcd: 353")
    assert plan.intent == "fun.xkcd_comic"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "fun.xkcd_comic"
    assert plan.risk == RiskLevel.MEDIUM


def test_itunes_search_route():
    settings = Settings.load()
    plan = route(settings, "itunes: beatles")
    assert plan.intent == "music.itunes_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "music.itunes_search"
    assert plan.risk == RiskLevel.MEDIUM


def test_gutendex_search_route():
    settings = Settings.load()
    plan = route(settings, "gutenberg: sherlock holmes")
    assert plan.intent == "books.gutendex_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "books.gutendex_search"
    assert plan.risk == RiskLevel.MEDIUM


def test_openfoodfacts_search_route():
    settings = Settings.load()
    plan = route(settings, "openfoodfacts: nutella")
    assert plan.intent == "data.openfoodfacts_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "data.openfoodfacts_search"
    assert plan.risk == RiskLevel.MEDIUM


def test_npm_downloads_last_week_route():
    settings = Settings.load()
    plan = route(settings, "npm downloads: express")
    assert plan.intent == "pkg.npm_downloads_last_week"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "pkg.npm_downloads_last_week"
    assert plan.risk == RiskLevel.MEDIUM


def test_geo_geocode_onde_fica_route():
    settings = Settings.load()
    plan = route(settings, "onde fica MASP?")
    assert plan.intent == "geo.geocode"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "geo.geocode"
    assert plan.risk == RiskLevel.MEDIUM


def test_googlebooks_search_route():
    settings = Settings.load()
    plan = route(settings, "gbooks: clean code")
    assert plan.intent == "books.googlebooks_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "books.googlebooks_search"
    assert plan.risk == RiskLevel.MEDIUM


def test_quote_random_route():
    settings = Settings.load()
    plan = route(settings, "quote")
    assert plan.intent == "fun.quote_random"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "fun.quote_random"
    assert plan.risk == RiskLevel.MEDIUM


def test_advice_route():
    settings = Settings.load()
    plan = route(settings, "conselho")
    assert plan.intent == "fun.advice"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "fun.advice"
    assert plan.risk == RiskLevel.MEDIUM


def test_bored_activity_route():
    settings = Settings.load()
    plan = route(settings, "entediado")
    assert plan.intent == "fun.bored_activity"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "fun.bored_activity"
    assert plan.risk == RiskLevel.MEDIUM


def test_fox_image_route():
    settings = Settings.load()
    plan = route(settings, "raposa")
    assert plan.intent == "fun.fox_image"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "fun.fox_image"
    assert plan.risk == RiskLevel.MEDIUM


def test_duck_image_route():
    settings = Settings.load()
    plan = route(settings, "pato imagem")
    assert plan.intent == "fun.duck_image"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "fun.duck_image"
    assert plan.risk == RiskLevel.MEDIUM


def test_datamuse_synonyms_route():
    settings = Settings.load()
    plan = route(settings, "sinônimos de rápido")
    assert plan.intent == "language.datamuse_related_words"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "language.datamuse_related_words"
    assert plan.risk == RiskLevel.MEDIUM


def test_scryfall_search_route():
    settings = Settings.load()
    plan = route(settings, "scryfall: lightning bolt")
    assert plan.intent == "cards.scryfall_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "cards.scryfall_search"
    assert plan.risk == RiskLevel.MEDIUM


def test_scryfall_random_route():
    settings = Settings.load()
    plan = route(settings, "mtg random")
    assert plan.intent == "cards.scryfall_random"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "cards.scryfall_random"
    assert plan.risk == RiskLevel.MEDIUM


def test_rickmorty_character_search_route():
    settings = Settings.load()
    plan = route(settings, "rickmorty: rick")
    assert plan.intent == "media.rickmorty_character_search"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "media.rickmorty_character_search"
    assert plan.risk == RiskLevel.MEDIUM


def test_sunrise_sunset_route():
    settings = Settings.load()
    plan = route(settings, "sunrise: -23.55, -46.63")
    assert plan.intent == "time.sunrise_sunset"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "time.sunrise_sunset"
    assert plan.risk == RiskLevel.MEDIUM


def test_dadjoke_route():
    settings = Settings.load()
    plan = route(settings, "dadjoke")
    assert plan.intent == "fun.dadjoke"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "fun.dadjoke"
    assert plan.risk == RiskLevel.MEDIUM


def test_jokeapi_route():
    settings = Settings.load()
    plan = route(settings, "jokeapi")
    assert plan.intent == "fun.jokeapi"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "fun.jokeapi"
    assert plan.risk == RiskLevel.MEDIUM


def test_ibge_states_route():
    settings = Settings.load()
    plan = route(settings, "ibge estados")
    assert plan.intent == "br.ibge_states"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "br.ibge_states"
    assert plan.risk == RiskLevel.MEDIUM


def test_ibge_municipalities_by_uf_route():
    settings = Settings.load()
    plan = route(settings, "ibge municipios: sp")
    assert plan.intent == "br.ibge_municipalities_by_uf"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "br.ibge_municipalities_by_uf"
    assert plan.risk == RiskLevel.MEDIUM


def test_viacep_lookup_route():
    settings = Settings.load()
    plan = route(settings, "cep: 01001-000")
    assert plan.intent == "br.viacep_lookup"
    assert plan.tool_calls and plan.tool_calls[0].tool_name == "br.viacep_lookup"
    assert plan.risk == RiskLevel.MEDIUM
