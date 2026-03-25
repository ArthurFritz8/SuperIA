"""Integrações com APIs públicas (read-only) via HTTP.

Objetivo:
- Dar ao agente acesso a fontes externas úteis (conhecimento e dados) sem depender de automação de navegador.

Princípios:
- Read-only.
- Guardrails de rede: allowlist de hosts, HTTPS, timeout baixo.
- Saídas enxutas (texto/JSON pequeno) para caber no loop.

Ferramentas:
- knowledge.wikipedia_summary
- data.weather_open_meteo
- finance.crypto_price
- papers.arxiv_search
- web.search (Tavily, opcional via OMNI_TAVILY_API_KEY)

Extras (sem chave, sujeito a rate-limit dos serviços):
- geo.geocode (OpenStreetMap / Nominatim)
- geo.reverse_geocode (OpenStreetMap / Nominatim)
- geo.route_osrm (OSRM demo + Nominatim)
- finance.fx_convert (Frankfurter)
- data.country_info (RestCountries)
- time.world_time (WorldTimeAPI)
- news.gdelt_search (GDELT)
- books.openlibrary_search (OpenLibrary)
- calendar.holidays (Nager.Date)
- finance.fear_greed_index (Alternative.me)
- science.earthquake_usgs (USGS)
- space.iss_position (WhereTheISS)
- health.covid_stats (disease.sh)
- knowledge.openalex_works_search (OpenAlex)
- knowledge.wikidata_search (Wikidata)
- knowledge.wikidata_entity (Wikidata)
- data.worldbank_indicator (World Bank)

Mais extras (sem chave, sujeito a rate-limit):
- news.hackernews_front_page (Hacker News via Algolia)
- code.github_repo_search (GitHub Search)
- qa.stackexchange_search (StackExchange / StackOverflow)
- language.dictionary_define (DictionaryAPI)
- media.lyrics (lyrics.ovh)
- fun.joke (Official Joke API)
- fun.trivia (Open Trivia DB)
- fun.pokemon_info (PokeAPI)
- net.ip_info (ipapi.co)
- people.random_user (randomuser.me)
- fun.cat_fact (catfact.ninja)
- utils.qr_code_url (QRServer — gera URL)

Tech/Dev (sem chave):
- sec.osv_vuln (OSV.dev — busca vulnerabilidade por ID)
- sec.osv_query (OSV.dev — vulnerabilidades por pacote+versão)
- pkg.pypi_project (PyPI — metadados do projeto)
- pkg.npm_package (NPM Registry — metadados do pacote)
- pkg.cratesio_crate (crates.io — metadados do crate)
- net.dns_google_resolve (DNS-over-HTTPS do Google)
- status.github (GitHub Status)

Infra/Sec (sem chave):
- net.rdap_domain (RDAP por domínio)
- net.rdap_ip (RDAP por IP)
- net.bgpview_ip (BGP/ASN por IP)
- net.bgpview_asn (Info por ASN)
- sec.crtsh_search (Certificate Transparency via crt.sh)
- sec.cisa_kev_search (CISA Known Exploited Vulnerabilities catalog)
- status.cloudflare (Cloudflare Status)
- status.discord (Discord Status)

Infra/Sec (mais, sem chave):
- net.ripestat_ip (RIPEstat — info de rede/ASN por IP)
- net.ripestat_asn (RIPEstat — overview por ASN)
- net.peeringdb_asn (PeeringDB — info por ASN)
- sec.urlhaus_url (URLhaus — reputação/relato por URL)
- sec.urlhaus_host (URLhaus — reputação/relato por host/domínio)
- sec.threatfox_ioc_search (ThreatFox — busca IOC)
- status.npm (Status do npm)
- status.openai (Status da OpenAI)
- status.docker (Docker Status via Status.io)
- sec.feodotracker_ip_blocklist (Feodo Tracker — lista IP:porta de botnet C2)
- sec.hashlookup (CIRCL Hashlookup — lookup de hash)
- status.atlassian (Atlassian Status)
- status.zoom (Zoom Status)

Mais APIs variadas (sem chave):
- space.spacex_latest_launch (SpaceX — último lançamento)
- archive.archiveorg_search (Archive.org — busca em acervo)
- media.tvmaze_search (TVMaze — busca séries)
- food.meal_search (TheMealDB — busca receitas)
- edu.universities_search (Hipolabs — busca universidades)
- people.agify_name (Agify — idade provável por nome)
- people.genderize_name (Genderize — gênero provável por nome)
- people.nationalize_name (Nationalize — nacionalidade provável por nome)
- fun.dog_image (Dog CEO — imagem aleatória)
- status.gitlab (GitLab Status)

Mais APIs variadas (sem chave) — lote 2:
- anime.jikan_search (Jikan — busca anime)
- art.met_search (Met Museum — busca no acervo)
- art.met_object (Met Museum — detalhe de um item)
- art.artic_search (Art Institute of Chicago — busca obras)
- chess.chesscom_player (Chess.com — perfil do jogador)
- chess.chesscom_stats (Chess.com — stats do jogador)
- chess.chesscom_daily_puzzle (Chess.com — puzzle diário)
- drink.openbrewerydb_search (Open Brewery DB — busca cervejarias)
- fun.deck_draw (Deck of Cards — sacar cartas)

Mais APIs variadas (sem chave) — lote 3:
- fun.xkcd_latest (xkcd — última tirinha)
- fun.xkcd_comic (xkcd — tirinha por número)
- music.itunes_search (Apple iTunes Search API)
- books.gutendex_search (Project Gutenberg via Gutendex)
- data.openfoodfacts_search (OpenFoodFacts — busca produtos)
- pkg.npm_downloads_last_week (npm downloads — last-week)

Mais APIs variadas (sem chave) — lote 4:
- books.googlebooks_search (Google Books — busca livros)
- fun.quote_random (Quotable — quote aleatória)
- fun.advice (Advice Slip — conselho aleatório)
- fun.bored_activity (Bored API — sugestão aleatória)
- fun.fox_image (RandomFox — imagem aleatória)
- fun.duck_image (RandomDuck — imagem aleatória)

Mais APIs variadas (sem chave) — lote 5:
- language.datamuse_related_words (Datamuse — palavras relacionadas/sinônimos)
- cards.scryfall_search (Scryfall — busca cartas de Magic)
- cards.scryfall_random (Scryfall — carta aleatória)
- media.rickmorty_character_search (Rick and Morty API — busca personagens)
- time.sunrise_sunset (Sunrise-Sunset — horários do sol por lat/lon)
- fun.dadjoke (icanhazdadjoke — piada aleatória)
- fun.jokeapi (JokeAPI — piada aleatória com safe-mode)
- br.ibge_states (IBGE — lista de estados)
- br.ibge_municipalities_by_uf (IBGE — municípios por UF)
- br.viacep_lookup (ViaCEP — endereço por CEP)
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
import html
from datetime import datetime, timedelta, timezone
from typing import Any, cast
from urllib.parse import quote

import httpx

from omniscia.core.tools import ToolRegistry, ToolSpec
from omniscia.core.types import ToolResult


def _normalize(text: str) -> str:
    # Normalização simples para busca case/acentos-insensível.
    t = unicodedata.normalize("NFKD", text)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = t.casefold()
    t = re.sub(r"\s+", " ", t).strip()
    return t


_ALLOWED_HOSTS = {
    # Wikipedia REST summary
    "pt.wikipedia.org",
    "en.wikipedia.org",
    # Open-Meteo
    "geocoding-api.open-meteo.com",
    "api.open-meteo.com",
    # CoinGecko
    "api.coingecko.com",
    # arXiv
    "export.arxiv.org",
    # Tavily
    "api.tavily.com",
    # DuckDuckGo (fallback web search, sem chave)
    "duckduckgo.com",
    "html.duckduckgo.com",
    # OpenStreetMap / Nominatim
    "nominatim.openstreetmap.org",
    # OSRM demo
    "router.project-osrm.org",
    # Frankfurter (FX)
    "api.frankfurter.app",
    # RestCountries
    "restcountries.com",
    # WorldTimeAPI
    "worldtimeapi.org",
    # GDELT
    "api.gdeltproject.org",
    # OpenLibrary
    "openlibrary.org",
    # Nager.Date
    "date.nager.at",
    # Crossref
    "api.crossref.org",
    # Alternative.me (Fear & Greed)
    "api.alternative.me",
    # USGS Earthquakes
    "earthquake.usgs.gov",
    # ISS position
    "api.wheretheiss.at",
    # COVID stats
    "disease.sh",
    # OpenAlex
    "api.openalex.org",
    # Wikidata
    "www.wikidata.org",
    # World Bank
    "api.worldbank.org",
    # Hacker News (Algolia)
    "hn.algolia.com",
    # GitHub public API
    "api.github.com",
    # StackExchange
    "api.stackexchange.com",
    # Free dictionary
    "api.dictionaryapi.dev",
    # Lyrics
    "api.lyrics.ovh",
    # Jokes
    "official-joke-api.appspot.com",
    # Trivia
    "opentdb.com",
    # PokeAPI
    "pokeapi.co",
    # IP info
    "ipapi.co",
    # Random user
    "randomuser.me",
    # Cat facts
    "catfact.ninja",
    # QR code
    "api.qrserver.com",
    # OSV.dev
    "api.osv.dev",
    # PyPI
    "pypi.org",
    # npm registry
    "registry.npmjs.org",
    # crates.io
    "crates.io",
    # DNS-over-HTTPS (Google)
    "dns.google",
    # GitHub Status
    "www.githubstatus.com",
    # RDAP proxy
    "rdap.org",
    # BGPView
    "api.bgpview.io",
    # Certificate Transparency search
    "crt.sh",
    # CISA KEV catalog
    "www.cisa.gov",
    # Cloudflare status (Statuspage)
    "www.cloudflarestatus.com",
    # Discord status (Statuspage)
    "discordstatus.com",
    # RIPEstat
    "stat.ripe.net",
    # PeeringDB
    "www.peeringdb.com",
    # URLhaus / ThreatFox (abuse.ch)
    "urlhaus-api.abuse.ch",
    "threatfox-api.abuse.ch",
    # npm Status (Statuspage)
    "status.npmjs.org",
    # OpenAI Status (Statuspage)
    "status.openai.com",
    # Docker Status (Status.io)
    "www.dockerstatus.com",
    # Feodo Tracker (abuse.ch)
    "feodotracker.abuse.ch",
    # CIRCL Hashlookup
    "hashlookup.circl.lu",
    # Atlassian Status (Statuspage)
    "status.atlassian.com",
    # Zoom Status (Statuspage)
    "status.zoom.us",
    # SpaceX
    "api.spacexdata.com",
    # Archive.org
    "archive.org",
    # TVMaze
    "api.tvmaze.com",
    # TheMealDB
    "www.themealdb.com",
    # Universities (Hipolabs)
    "universities.hipolabs.com",
    # Agify/Genderize/Nationalize
    "api.agify.io",
    "api.genderize.io",
    "api.nationalize.io",
    # Dog API
    "dog.ceo",
    # GitLab Status
    "status.gitlab.com",
    # Jikan (Anime)
    "api.jikan.moe",
    # Met Museum
    "collectionapi.metmuseum.org",
    # Art Institute of Chicago
    "api.artic.edu",
    # Chess.com
    "api.chess.com",
    # Open Brewery DB
    "api.openbrewerydb.org",
    # Deck of Cards
    "deckofcardsapi.com",
    # xkcd
    "xkcd.com",
    # iTunes Search
    "itunes.apple.com",
    # Gutendex (Project Gutenberg)
    "gutendex.com",
    # OpenFoodFacts
    "world.openfoodfacts.org",
    # npm downloads API
    "api.npmjs.org",
    # Google Books
    "www.googleapis.com",
    # Quotable
    "api.quotable.io",
    # Advice Slip
    "api.adviceslip.com",
    # Bored API
    "www.boredapi.com",
    # RandomFox
    "randomfox.ca",
    # RandomDuck
    "random-d.uk",
    # Datamuse
    "api.datamuse.com",
    # Scryfall (Magic: The Gathering)
    "api.scryfall.com",
    # Rick and Morty
    "rickandmortyapi.com",
    # Sunrise-Sunset
    "api.sunrise-sunset.org",
    # icanhazdadjoke
    "icanhazdadjoke.com",
    # JokeAPI
    "v2.jokeapi.dev",
    # IBGE
    "servicodados.ibge.gov.br",
    # ViaCEP
    "viacep.com.br",
}


def register_public_api_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="knowledge.wikipedia_summary",
            description="Busca resumo na Wikipedia (REST). Args: title|query, lang? (pt/en)",
            risk="MEDIUM",
            fn=_wikipedia_summary,
        )
    )

    registry.register(
        ToolSpec(
            name="data.weather_open_meteo",
            description=(
                "Clima atual por cidade (Open-Meteo). Args: city, country_code? (ex: BR), lang? (pt)") ,
            risk="MEDIUM",
            fn=_weather_open_meteo,
        )
    )

    registry.register(
        ToolSpec(
            name="finance.crypto_price",
            description=(
                "Preço de cripto via CoinGecko. Args: asset (ex: bitcoin|btc|ethereum|eth), vs? (usd|brl|eur, default brl,usd)"
            ),
            risk="MEDIUM",
            fn=_crypto_price,
        )
    )

    registry.register(
        ToolSpec(
            name="finance.crypto_market_chart",
            description=(
                "Série histórica (gráfico) de cripto via CoinGecko. Args: asset (nome/símbolo), vs? (usd|brl|eur, default usd), days? (1|7|30|90|180|365|max, default 30)"
            ),
            risk="MEDIUM",
            fn=_crypto_market_chart,
        )
    )

    registry.register(
        ToolSpec(
            name="papers.arxiv_search",
            description="Busca papers no arXiv (ATOM). Args: query, max_results? (default 5)",
            risk="MEDIUM",
            fn=_arxiv_search,
        )
    )

    registry.register(
        ToolSpec(
            name="web.search",
            description=(
                "Busca web (Tavily se OMNI_TAVILY_API_KEY estiver configurada; senão fallback DuckDuckGo). "
                "Args: query, max_results?, depth? (basic|advanced; Tavily)"
            ),
            risk="MEDIUM",
            fn=_web_search,
        )
    )

    registry.register(
        ToolSpec(
            name="geo.geocode",
            description="Geocoding (texto -> lat/lon) via OpenStreetMap Nominatim. Args: query, lang? (pt/en), country_codes? (ex: br)",
            risk="MEDIUM",
            fn=_geo_geocode,
        )
    )

    registry.register(
        ToolSpec(
            name="geo.reverse_geocode",
            description="Reverse geocoding (lat/lon -> endereço) via OpenStreetMap Nominatim. Args: lat, lon, lang? (pt/en)",
            risk="MEDIUM",
            fn=_geo_reverse_geocode,
        )
    )

    registry.register(
        ToolSpec(
            name="geo.route_osrm",
            description=(
                "Rota via OSRM demo (usa Nominatim para geocoding). Args: from, to, profile? (driving|walking|cycling), lang? (pt/en)"
            ),
            risk="MEDIUM",
            fn=_geo_route_osrm,
        )
    )

    registry.register(
        ToolSpec(
            name="finance.fx_convert",
            description="Converte moedas via Frankfurter (ECB). Args: amount, from, to",
            risk="MEDIUM",
            fn=_fx_convert,
        )
    )

    registry.register(
        ToolSpec(
            name="data.country_info",
            description="Informações de país via RestCountries. Args: name|query (ex: Brazil), fields? (csv)",
            risk="MEDIUM",
            fn=_country_info,
        )
    )

    registry.register(
        ToolSpec(
            name="time.world_time",
            description="Hora atual por timezone via WorldTimeAPI. Args: tz (ex: America/Sao_Paulo)",
            risk="MEDIUM",
            fn=_world_time,
        )
    )

    registry.register(
        ToolSpec(
            name="news.gdelt_search",
            description="Busca notícias via GDELT. Args: query, max_results? (default 5), lang? (ex: Portuguese)",
            risk="MEDIUM",
            fn=_gdelt_search,
        )
    )

    registry.register(
        ToolSpec(
            name="books.openlibrary_search",
            description="Busca livros via OpenLibrary. Args: query, max_results? (default 5)",
            risk="MEDIUM",
            fn=_openlibrary_search,
        )
    )

    registry.register(
        ToolSpec(
            name="calendar.holidays",
            description="Feriados públicos via Nager.Date. Args: year, country_code (ex: BR)",
            risk="MEDIUM",
            fn=_holidays,
        )
    )

    registry.register(
        ToolSpec(
            name="papers.crossref_search",
            description="Busca works no Crossref (papers/DOIs). Args: query, rows? (default 5)",
            risk="MEDIUM",
            fn=_crossref_search,
        )
    )

    registry.register(
        ToolSpec(
            name="finance.fear_greed_index",
            description="Índice Fear & Greed (Alternative.me). Args: limit? (default 1)",
            risk="MEDIUM",
            fn=_fear_greed_index,
        )
    )

    registry.register(
        ToolSpec(
            name="science.earthquake_usgs",
            description="Terremotos recentes via USGS (GeoJSON). Args: days? (default 7), min_magnitude? (default 4.5), limit? (default 10)",
            risk="MEDIUM",
            fn=_earthquake_usgs,
        )
    )

    registry.register(
        ToolSpec(
            name="space.iss_position",
            description="Posição atual da ISS via WhereTheISS. Args: (none)",
            risk="MEDIUM",
            fn=_iss_position,
        )
    )

    registry.register(
        ToolSpec(
            name="health.covid_stats",
            description="Estatísticas COVID via disease.sh. Args: country? (ex: Brazil) ou vazio para global",
            risk="MEDIUM",
            fn=_covid_stats,
        )
    )

    registry.register(
        ToolSpec(
            name="knowledge.openalex_works_search",
            description="Busca works/papers via OpenAlex. Args: query, max_results? (default 5)",
            risk="MEDIUM",
            fn=_openalex_works_search,
        )
    )

    registry.register(
        ToolSpec(
            name="knowledge.wikidata_search",
            description="Busca entidades no Wikidata. Args: query, lang? (pt/en), limit? (default 5)",
            risk="MEDIUM",
            fn=_wikidata_search,
        )
    )

    registry.register(
        ToolSpec(
            name="knowledge.wikidata_entity",
            description="Baixa JSON de uma entidade Wikidata (ex: Q42). Args: id",
            risk="MEDIUM",
            fn=_wikidata_entity,
        )
    )

    registry.register(
        ToolSpec(
            name="data.worldbank_indicator",
            description="Consulta indicador do World Bank. Args: country_code (ex: BR), indicator (ex: SP.POP.TOTL), date? (ex: 2010:2024)",
            risk="MEDIUM",
            fn=_worldbank_indicator,
        )
    )

    registry.register(
        ToolSpec(
            name="news.hackernews_front_page",
            description="Top/front page do Hacker News (Algolia). Args: limit? (default 10)",
            risk="MEDIUM",
            fn=_hackernews_front_page,
        )
    )

    registry.register(
        ToolSpec(
            name="code.github_repo_search",
            description="Busca repositórios no GitHub. Args: query, limit? (default 5)",
            risk="MEDIUM",
            fn=_github_repo_search,
        )
    )

    registry.register(
        ToolSpec(
            name="qa.stackexchange_search",
            description="Busca perguntas no StackOverflow (StackExchange). Args: query, limit? (default 5)",
            risk="MEDIUM",
            fn=_stackexchange_search,
        )
    )

    registry.register(
        ToolSpec(
            name="language.dictionary_define",
            description="Define palavra via Free Dictionary API. Args: term, lang? (en default)",
            risk="MEDIUM",
            fn=_dictionary_define,
        )
    )

    registry.register(
        ToolSpec(
            name="media.lyrics",
            description="Busca letra (lyrics) via lyrics.ovh. Args: artist, title",
            risk="MEDIUM",
            fn=_lyrics,
        )
    )

    registry.register(
        ToolSpec(
            name="fun.joke",
            description="Retorna uma piada (Official Joke API). Args: (none)",
            risk="MEDIUM",
            fn=_joke,
        )
    )

    registry.register(
        ToolSpec(
            name="fun.trivia",
            description="Perguntas de trivia (Open Trivia DB). Args: amount? (default 5), difficulty? (easy|medium|hard), type? (multiple|boolean)",
            risk="MEDIUM",
            fn=_trivia,
        )
    )

    registry.register(
        ToolSpec(
            name="fun.pokemon_info",
            description="Info de Pokémon via PokeAPI. Args: name_or_id (ex: pikachu|25)",
            risk="MEDIUM",
            fn=_pokemon_info,
        )
    )

    registry.register(
        ToolSpec(
            name="net.ip_info",
            description="Info/geo de IP via ipapi.co. Args: ip? (opcional) ou vazio para IP atual",
            risk="MEDIUM",
            fn=_ip_info,
        )
    )

    registry.register(
        ToolSpec(
            name="people.random_user",
            description="Gera um perfil de pessoa aleatória via randomuser.me. Args: nat? (ex: BR), gender? (male|female)",
            risk="MEDIUM",
            fn=_random_user,
        )
    )

    registry.register(
        ToolSpec(
            name="fun.cat_fact",
            description="Retorna um fato aleatório sobre gatos. Args: (none)",
            risk="MEDIUM",
            fn=_cat_fact,
        )
    )

    registry.register(
        ToolSpec(
            name="utils.qr_code_url",
            description="Gera URL de QR code (imagem) via QRServer sem baixar o arquivo. Args: data, size? (ex: 200x200)",
            risk="MEDIUM",
            fn=_qr_code_url,
        )
    )

    registry.register(
        ToolSpec(
            name="sec.osv_vuln",
            description="Busca vulnerabilidade por ID no OSV.dev (ex: GHSA-xxxx-xxxx-xxxx, OSV-2020-744, CVE-2024-xxxx). Args: id",
            risk="MEDIUM",
            fn=_osv_vuln,
        )
    )

    registry.register(
        ToolSpec(
            name="sec.osv_query",
            description="Lista vulnerabilidades por pacote+versão via OSV.dev. Args: ecosystem (ex: PyPI|npm|crates.io), name, version, limit? (default 10)",
            risk="MEDIUM",
            fn=_osv_query,
        )
    )

    registry.register(
        ToolSpec(
            name="pkg.pypi_project",
            description="Metadados de projeto no PyPI. Args: name (ex: requests)",
            risk="MEDIUM",
            fn=_pypi_project,
        )
    )

    registry.register(
        ToolSpec(
            name="pkg.npm_package",
            description="Metadados de pacote npm via registry.npmjs.org. Args: name (ex: express ou @scope/name)",
            risk="MEDIUM",
            fn=_npm_package,
        )
    )

    registry.register(
        ToolSpec(
            name="pkg.cratesio_crate",
            description="Metadados de crate no crates.io. Args: name (ex: tokio)",
            risk="MEDIUM",
            fn=_cratesio_crate,
        )
    )

    registry.register(
        ToolSpec(
            name="net.dns_google_resolve",
            description="Resolve DNS via Google DNS-over-HTTPS. Args: name, type? (A|AAAA|CNAME|MX|TXT, default A)",
            risk="MEDIUM",
            fn=_dns_google_resolve,
        )
    )

    registry.register(
        ToolSpec(
            name="status.github",
            description="Status atual do GitHub (githubstatus.com). Args: (none)",
            risk="MEDIUM",
            fn=_github_status,
        )
    )

    registry.register(
        ToolSpec(
            name="net.rdap_domain",
            description="Consulta RDAP (whois moderno) por domínio. Args: domain (ex: example.com)",
            risk="MEDIUM",
            fn=_rdap_domain,
        )
    )

    registry.register(
        ToolSpec(
            name="net.rdap_ip",
            description="Consulta RDAP (whois moderno) por IP. Args: ip (IPv4)",
            risk="MEDIUM",
            fn=_rdap_ip,
        )
    )

    registry.register(
        ToolSpec(
            name="net.bgpview_ip",
            description="Consulta BGP/ASN por IP via bgpview.io. Args: ip (IPv4)",
            risk="MEDIUM",
            fn=_bgpview_ip,
        )
    )

    registry.register(
        ToolSpec(
            name="net.bgpview_asn",
            description="Consulta dados por ASN via bgpview.io. Args: asn (ex: 15169)",
            risk="MEDIUM",
            fn=_bgpview_asn,
        )
    )

    registry.register(
        ToolSpec(
            name="sec.crtsh_search",
            description="Busca em Certificate Transparency via crt.sh. Args: query (ex: example.com), limit? (default 10)",
            risk="MEDIUM",
            fn=_crtsh_search,
        )
    )

    registry.register(
        ToolSpec(
            name="sec.cisa_kev_search",
            description="Busca no catálogo CISA KEV. Args: query (texto ou CVE), limit? (default 10)",
            risk="MEDIUM",
            fn=_cisa_kev_search,
        )
    )

    registry.register(
        ToolSpec(
            name="status.cloudflare",
            description="Status atual do Cloudflare (cloudflarestatus.com). Args: (none)",
            risk="MEDIUM",
            fn=_cloudflare_status,
        )
    )

    registry.register(
        ToolSpec(
            name="status.discord",
            description="Status atual do Discord (discordstatus.com). Args: (none)",
            risk="MEDIUM",
            fn=_discord_status,
        )
    )

    registry.register(
        ToolSpec(
            name="net.ripestat_ip",
            description="Consulta RIPEstat por IP (network-info). Args: ip (IPv4)",
            risk="MEDIUM",
            fn=_ripestat_ip,
        )
    )

    registry.register(
        ToolSpec(
            name="net.ripestat_asn",
            description="Consulta RIPEstat por ASN (as-overview). Args: asn (ex: 15169)",
            risk="MEDIUM",
            fn=_ripestat_asn,
        )
    )

    registry.register(
        ToolSpec(
            name="net.peeringdb_asn",
            description="Consulta PeeringDB por ASN. Args: asn (ex: 15169)",
            risk="MEDIUM",
            fn=_peeringdb_asn,
        )
    )

    registry.register(
        ToolSpec(
            name="sec.urlhaus_url",
            description="Consulta URLhaus por URL. Args: url (ex: http://example.com/path)",
            risk="MEDIUM",
            fn=_urlhaus_url,
        )
    )

    registry.register(
        ToolSpec(
            name="sec.urlhaus_host",
            description="Consulta URLhaus por host/domínio. Args: host (ex: example.com)",
            risk="MEDIUM",
            fn=_urlhaus_host,
        )
    )

    registry.register(
        ToolSpec(
            name="sec.threatfox_ioc_search",
            description="Busca IOC no ThreatFox (abuse.ch). Args: ioc (texto), limit? (default 10)",
            risk="MEDIUM",
            fn=_threatfox_ioc_search,
        )
    )

    registry.register(
        ToolSpec(
            name="status.npm",
            description="Status atual do npm (status.npmjs.org). Args: (none)",
            risk="MEDIUM",
            fn=_npm_status,
        )
    )

    registry.register(
        ToolSpec(
            name="status.openai",
            description="Status atual da OpenAI (status.openai.com). Args: (none)",
            risk="MEDIUM",
            fn=_openai_status,
        )
    )

    registry.register(
        ToolSpec(
            name="status.docker",
            description="Status atual do Docker (dockerstatus.com via Status.io). Args: (none)",
            risk="MEDIUM",
            fn=_docker_status,
        )
    )

    registry.register(
        ToolSpec(
            name="sec.feodotracker_ip_blocklist",
            description="Lista IP:porta de botnet C2 (Feodo Tracker). Args: limit? (default 20)",
            risk="MEDIUM",
            fn=_feodotracker_ip_blocklist,
        )
    )

    registry.register(
        ToolSpec(
            name="sec.hashlookup",
            description="Lookup de hash no CIRCL Hashlookup. Args: algorithm (md5|sha1|sha256), hash",
            risk="MEDIUM",
            fn=_hashlookup,
        )
    )

    registry.register(
        ToolSpec(
            name="status.atlassian",
            description="Status atual da Atlassian (status.atlassian.com). Args: (none)",
            risk="MEDIUM",
            fn=_atlassian_status,
        )
    )

    registry.register(
        ToolSpec(
            name="status.zoom",
            description="Status atual do Zoom (status.zoom.us). Args: (none)",
            risk="MEDIUM",
            fn=_zoom_status,
        )
    )

    registry.register(
        ToolSpec(
            name="space.spacex_latest_launch",
            description="Último lançamento da SpaceX. Args: (none)",
            risk="MEDIUM",
            fn=_spacex_latest_launch,
        )
    )

    registry.register(
        ToolSpec(
            name="archive.archiveorg_search",
            description="Busca no Archive.org (advancedsearch). Args: query, limit? (default 5)",
            risk="MEDIUM",
            fn=_archiveorg_search,
        )
    )

    registry.register(
        ToolSpec(
            name="media.tvmaze_search",
            description="Busca séries no TVMaze. Args: query, limit? (default 5)",
            risk="MEDIUM",
            fn=_tvmaze_search,
        )
    )

    registry.register(
        ToolSpec(
            name="food.meal_search",
            description="Busca receitas no TheMealDB. Args: query, limit? (default 5)",
            risk="MEDIUM",
            fn=_mealdb_search,
        )
    )

    registry.register(
        ToolSpec(
            name="edu.universities_search",
            description="Busca universidades (Hipolabs). Args: name, country? (opcional), limit? (default 10)",
            risk="MEDIUM",
            fn=_universities_search,
        )
    )

    registry.register(
        ToolSpec(
            name="people.agify_name",
            description="Idade provável por nome (Agify). Args: name, country_code? (2 letras)",
            risk="MEDIUM",
            fn=_agify_name,
        )
    )

    registry.register(
        ToolSpec(
            name="people.genderize_name",
            description="Gênero provável por nome (Genderize). Args: name, country_code? (2 letras)",
            risk="MEDIUM",
            fn=_genderize_name,
        )
    )

    registry.register(
        ToolSpec(
            name="people.nationalize_name",
            description="Nacionalidade provável por nome (Nationalize). Args: name, limit? (default 5)",
            risk="MEDIUM",
            fn=_nationalize_name,
        )
    )

    registry.register(
        ToolSpec(
            name="fun.dog_image",
            description="Imagem aleatória de cachorro (dog.ceo). Args: (none)",
            risk="MEDIUM",
            fn=_dog_image,
        )
    )

    registry.register(
        ToolSpec(
            name="status.gitlab",
            description="Status atual do GitLab (status.gitlab.com). Args: (none)",
            risk="MEDIUM",
            fn=_gitlab_status,
        )
    )

    registry.register(
        ToolSpec(
            name="anime.jikan_search",
            description="Busca animes via Jikan (MyAnimeList). Args: query, limit? (default 5)",
            risk="MEDIUM",
            fn=_jikan_anime_search,
        )
    )

    registry.register(
        ToolSpec(
            name="art.met_search",
            description="Busca no acervo do Met Museum. Args: query, limit? (default 5)",
            risk="MEDIUM",
            fn=_met_search,
        )
    )

    registry.register(
        ToolSpec(
            name="art.met_object",
            description="Detalhe de um item do Met Museum. Args: object_id",
            risk="MEDIUM",
            fn=_met_object,
        )
    )

    registry.register(
        ToolSpec(
            name="art.artic_search",
            description="Busca obras no Art Institute of Chicago. Args: query, limit? (default 5)",
            risk="MEDIUM",
            fn=_artic_search,
        )
    )

    registry.register(
        ToolSpec(
            name="chess.chesscom_player",
            description="Perfil de jogador no Chess.com. Args: username",
            risk="MEDIUM",
            fn=_chesscom_player,
        )
    )

    registry.register(
        ToolSpec(
            name="chess.chesscom_stats",
            description="Stats de jogador no Chess.com. Args: username",
            risk="MEDIUM",
            fn=_chesscom_stats,
        )
    )

    registry.register(
        ToolSpec(
            name="chess.chesscom_daily_puzzle",
            description="Puzzle diário do Chess.com. Args: (none)",
            risk="MEDIUM",
            fn=_chesscom_daily_puzzle,
        )
    )

    registry.register(
        ToolSpec(
            name="drink.openbrewerydb_search",
            description="Busca cervejarias via Open Brewery DB. Args: query, limit? (default 10)",
            risk="MEDIUM",
            fn=_openbrewerydb_search,
        )
    )

    registry.register(
        ToolSpec(
            name="fun.deck_draw",
            description="Saca cartas de um baralho novo. Args: count? (default 5)",
            risk="MEDIUM",
            fn=_deck_draw,
        )
    )

    registry.register(
        ToolSpec(
            name="fun.xkcd_latest",
            description="Última tirinha do xkcd. Args: (none)",
            risk="MEDIUM",
            fn=_xkcd_latest,
        )
    )

    registry.register(
        ToolSpec(
            name="fun.xkcd_comic",
            description="Tirinha do xkcd por número. Args: num",
            risk="MEDIUM",
            fn=_xkcd_comic,
        )
    )

    registry.register(
        ToolSpec(
            name="music.itunes_search",
            description="Busca músicas/podcasts/apps via iTunes Search API. Args: term|query, media? (music|podcast|all), limit? (default 5)",
            risk="MEDIUM",
            fn=_itunes_search,
        )
    )

    registry.register(
        ToolSpec(
            name="books.gutendex_search",
            description="Busca livros do Project Gutenberg via Gutendex. Args: query, limit? (default 5)",
            risk="MEDIUM",
            fn=_gutendex_search,
        )
    )

    registry.register(
        ToolSpec(
            name="data.openfoodfacts_search",
            description="Busca produtos no OpenFoodFacts. Args: query, limit? (default 5)",
            risk="MEDIUM",
            fn=_openfoodfacts_search,
        )
    )

    registry.register(
        ToolSpec(
            name="pkg.npm_downloads_last_week",
            description="Downloads last-week de um pacote npm. Args: package",
            risk="MEDIUM",
            fn=_npm_downloads_last_week,
        )
    )

    registry.register(
        ToolSpec(
            name="books.googlebooks_search",
            description="Busca livros no Google Books (sem chave). Args: query, limit? (default 5)",
            risk="MEDIUM",
            fn=_googlebooks_search,
        )
    )

    registry.register(
        ToolSpec(
            name="fun.quote_random",
            description="Quote aleatória (Quotable). Args: (none)",
            risk="MEDIUM",
            fn=_quote_random,
        )
    )

    registry.register(
        ToolSpec(
            name="fun.advice",
            description="Conselho aleatório (Advice Slip). Args: (none)",
            risk="MEDIUM",
            fn=_advice_random,
        )
    )

    registry.register(
        ToolSpec(
            name="fun.bored_activity",
            description="Sugestão aleatória de atividade (Bored API). Args: (none)",
            risk="MEDIUM",
            fn=_bored_activity,
        )
    )

    registry.register(
        ToolSpec(
            name="fun.fox_image",
            description="Imagem aleatória de raposa (RandomFox). Args: (none)",
            risk="MEDIUM",
            fn=_fox_image,
        )
    )

    registry.register(
        ToolSpec(
            name="fun.duck_image",
            description="Imagem aleatória de pato (RandomDuck). Args: (none)",
            risk="MEDIUM",
            fn=_duck_image,
        )
    )

    registry.register(
        ToolSpec(
            name="language.datamuse_related_words",
            description=(
                "Palavras relacionadas via Datamuse. Args: query, relation? (ml|rel_syn|rel_ant|rel_rhy, default ml), max_results? (default 10)"
            ),
            risk="MEDIUM",
            fn=_datamuse_related_words,
        )
    )

    registry.register(
        ToolSpec(
            name="cards.scryfall_search",
            description="Busca cartas no Scryfall (Magic). Args: query, limit? (default 5)",
            risk="MEDIUM",
            fn=_scryfall_search,
        )
    )

    registry.register(
        ToolSpec(
            name="cards.scryfall_random",
            description="Carta aleatória no Scryfall (Magic). Args: (none)",
            risk="MEDIUM",
            fn=_scryfall_random,
        )
    )

    registry.register(
        ToolSpec(
            name="media.rickmorty_character_search",
            description="Busca personagem de Rick and Morty. Args: query, limit? (default 5)",
            risk="MEDIUM",
            fn=_rickmorty_character_search,
        )
    )

    registry.register(
        ToolSpec(
            name="time.sunrise_sunset",
            description="Horários de nascer/pôr do sol (UTC) via Sunrise-Sunset. Args: lat, lon, date? (YYYY-MM-DD)",
            risk="MEDIUM",
            fn=_sunrise_sunset,
        )
    )

    registry.register(
        ToolSpec(
            name="fun.dadjoke",
            description="Piada aleatória (dad joke) via icanhazdadjoke. Args: (none)",
            risk="MEDIUM",
            fn=_dadjoke,
        )
    )

    registry.register(
        ToolSpec(
            name="fun.jokeapi",
            description="Piada aleatória via JokeAPI (safe-mode). Args: category? (default Any)",
            risk="MEDIUM",
            fn=_jokeapi,
        )
    )

    registry.register(
        ToolSpec(
            name="br.ibge_states",
            description="Lista estados do Brasil via IBGE. Args: (none)",
            risk="MEDIUM",
            fn=_ibge_states,
        )
    )

    registry.register(
        ToolSpec(
            name="br.ibge_municipalities_by_uf",
            description="Lista municípios por UF via IBGE. Args: uf (ex: SP), limit? (default 20)",
            risk="MEDIUM",
            fn=_ibge_municipalities_by_uf,
        )
    )

    registry.register(
        ToolSpec(
            name="br.viacep_lookup",
            description="Consulta endereço por CEP via ViaCEP. Args: cep (8 dígitos)",
            risk="MEDIUM",
            fn=_viacep_lookup,
        )
    )


def _default_headers() -> dict[str, str]:
    # Alguns serviços (ex.: Nominatim/Crossref) esperam um User-Agent identificável.
    ua = (os.getenv("OMNI_HTTP_USER_AGENT") or "").strip()
    if not ua:
        ua = "omniscia/0.1 (https://local)"
    accept_lang = (os.getenv("OMNI_HTTP_ACCEPT_LANGUAGE") or "").strip()
    h = {
        "User-Agent": ua,
        "Accept": "application/json",
    }
    if accept_lang:
        h["Accept-Language"] = accept_lang
    return h


def _http_json(
    *,
    method: str,
    url: str,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout_s: float = 12.0,
) -> tuple[Any | None, str | None]:
    try:
        u = httpx.URL(url)
        host = (u.host or "").lower()
        if u.scheme != "https":
            return None, "apenas https é permitido"
        if host not in _ALLOWED_HOSTS:
            return None, f"host não permitido: {host}"

        merged_headers = {**_default_headers(), **(headers or {})}

        with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
            resp = client.request(method.upper(), url, params=params, json=json_body, headers=merged_headers)
        if resp.status_code >= 400:
            return None, f"HTTP {resp.status_code}: {resp.text[:300]}"
        try:
            return resp.json(), None
        except Exception:
            return None, "resposta não é JSON"
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def _http_form(
    *,
    url: str,
    form_body: dict[str, Any],
    headers: dict[str, str] | None = None,
    timeout_s: float = 12.0,
) -> tuple[Any | None, str | None]:
    """HTTP POST com form data (application/x-www-form-urlencoded) retornando JSON."""
    try:
        u = httpx.URL(url)
        host = (u.host or "").lower()
        if u.scheme != "https":
            return None, "apenas https é permitido"
        if host not in _ALLOWED_HOSTS:
            return None, f"host não permitido: {host}"

        merged_headers = {**_default_headers(), **(headers or {})}
        # Força o server a responder JSON quando suportado.
        merged_headers.setdefault("Accept", "application/json")

        with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
            resp = client.post(url, data=form_body, headers=merged_headers)
        if resp.status_code >= 400:
            return None, f"HTTP {resp.status_code}: {resp.text[:300]}"
        try:
            return resp.json(), None
        except Exception:
            return None, "resposta não é JSON"
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def _http_text(
    *,
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout_s: float = 12.0,
) -> tuple[str | None, str | None]:
    """HTTP GET retornando texto (HTML/Plain)."""
    try:
        u = httpx.URL(url)
        host = (u.host or "").lower()
        if u.scheme != "https":
            return None, "apenas https é permitido"
        if host not in _ALLOWED_HOSTS:
            return None, f"host não permitido: {host}"

        merged_headers = {**_default_headers(), **(headers or {})}
        merged_headers.setdefault("Accept", "text/html, text/plain; q=0.9, */*; q=0.1")

        with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
            resp = client.get(url, params=params, headers=merged_headers)
        if resp.status_code >= 400:
            return None, f"HTTP {resp.status_code}: {resp.text[:300]}"
        return resp.text, None
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def _web_search(args: dict[str, Any]) -> ToolResult:
    """Busca web com fallback.

    Preferência:
    - Tavily quando OMNI_TAVILY_API_KEY está configurada.
    - Caso contrário, DuckDuckGo (HTML) sem chave.
    """

    api_key = (os.getenv("OMNI_TAVILY_API_KEY") or "").strip()
    if api_key:
        return _tavily_search(args)
    return _duckduckgo_search(args)


def _duckduckgo_search(args: dict[str, Any]) -> ToolResult:
    query = str(args.get("query", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe query")

    try:
        max_results = int(args.get("max_results", 5) or 5)
    except Exception:
        max_results = 5
    if max_results < 1:
        max_results = 1
    if max_results > 10:
        max_results = 10

    # Endpoint HTML simples (mais fácil de parsear e sem JS).
    text, err = _http_text(
        url="https://html.duckduckgo.com/html/",
        params={"q": query},
        headers={"Accept": "text/html"},
        timeout_s=12.0,
    )
    if err:
        return ToolResult(status="error", error=err)
    if not text:
        return ToolResult(status="error", error="resposta vazia")

    # Parse mínimo por regex (intencionalmente simples e best-effort).
    # Formato típico:
    # <a rel="nofollow" class="result__a" href="...">Title</a>
    # <a class="result__snippet">Snippet</a>
    titles_urls = re.findall(r"<a[^>]*class=\"result__a\"[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", text, flags=re.IGNORECASE | re.DOTALL)
    snippets = re.findall(r"<a[^>]*class=\"result__snippet\"[^>]*>(.*?)</a>", text, flags=re.IGNORECASE | re.DOTALL)

    def _clean(s: str) -> str:
        s2 = re.sub(r"<.*?>", "", s or "")
        s2 = html.unescape(s2)
        s2 = re.sub(r"\s+", " ", s2).strip()
        return s2

    slim: list[dict[str, Any]] = []
    for i, (url, title) in enumerate(titles_urls[:max_results]):
        t = _clean(title)[:160]
        u = html.unescape(url).strip()
        sn = _clean(snippets[i] if i < len(snippets) else "")[:600]
        if not u:
            continue
        slim.append({"title": t, "url": u, "content": sn, "source": "duckduckgo"})

    out = {"query": query, "results": slim}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _wikipedia_summary(args: dict[str, Any]) -> ToolResult:
    title = str(args.get("title") or args.get("query") or "").strip()
    if not title:
        return ToolResult(status="error", error="informe title (ou query)")

    lang = str(args.get("lang", "pt") or "pt").strip().lower()
    if lang not in {"pt", "en"}:
        lang = "pt"

    safe_title = quote(title.replace(" ", "_"), safe="")
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{safe_title}"

    data, err = _http_json(method="GET", url=url)
    if err:
        if str(err).startswith("HTTP 404"):
            out = {
                "title": title,
                "lang": lang,
                "url": "",
                "summary": "Página não encontrada na Wikipedia.",
            }
            return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))
        return ToolResult(status="error", error=err)

    assert data is not None
    extract = str(data.get("extract", "") or "").strip()
    page_url = ""
    try:
        page_url = str((((data.get("content_urls") or {}).get("desktop") or {}).get("page") or "")).strip()
    except Exception:
        page_url = ""

    if not extract:
        out = {
            "title": str(data.get("title", "") or title),
            "lang": lang,
            "url": page_url,
            "summary": "Sem resumo disponível (página não encontrada ou vazia).",
        }
        return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))

    out = {
        "title": str(data.get("title", "") or title),
        "lang": lang,
        "url": page_url,
        "summary": extract,
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _weather_open_meteo(args: dict[str, Any]) -> ToolResult:
    city = str(args.get("city", "") or "").strip()
    if not city:
        return ToolResult(status="error", error="informe city")

    lang = str(args.get("lang", "pt") or "pt").strip().lower() or "pt"
    country_code = str(args.get("country_code", "") or "").strip().upper()

    # Geocoding
    params: dict[str, Any] = {
        "name": city,
        "count": 1,
        "language": lang,
        "format": "json",
    }
    if country_code and re.fullmatch(r"[A-Z]{2}", country_code):
        params["country_code"] = country_code

    geo, err = _http_json(method="GET", url="https://geocoding-api.open-meteo.com/v1/search", params=params)
    if err:
        return ToolResult(status="error", error=err)

    results = (geo or {}).get("results") if isinstance(geo, dict) else None
    if not results:
        return ToolResult(status="error", error="cidade não encontrada")

    r0 = (results or [])[0] or {}
    lat = r0.get("latitude")
    lon = r0.get("longitude")
    if lat is None or lon is None:
        return ToolResult(status="error", error="geocoding incompleto")

    forecast_params = {
        "latitude": float(lat),
        "longitude": float(lon),
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m",
        "timezone": "auto",
    }
    wx, err2 = _http_json(method="GET", url="https://api.open-meteo.com/v1/forecast", params=forecast_params)
    if err2:
        return ToolResult(status="error", error=err2)

    current = (wx or {}).get("current") if isinstance(wx, dict) else None
    out = {
        "place": {
            "name": r0.get("name"),
            "admin1": r0.get("admin1"),
            "country": r0.get("country"),
            "latitude": float(lat),
            "longitude": float(lon),
        },
        "current": current or {},
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


_ASSET_ALIASES = {
    "btc": "bitcoin",
    "bitcoin": "bitcoin",
    "eth": "ethereum",
    "ethereum": "ethereum",
    "sol": "solana",
    "solana": "solana",
    "usdt": "tether",
    "tether": "tether",
    # Pi Network (best-effort id; pode variar conforme o CoinGecko)
    "pi": "pi-network",
    "pi network": "pi-network",
    "pi-network": "pi-network",
}


def _coingecko_find_coin_id(asset_query: str) -> tuple[str | None, str | None]:
    """Resolve um asset (nome/símbolo) para um coin id do CoinGecko (best-effort)."""

    q = (asset_query or "").strip().lower()
    if not q:
        return None, "informe asset"

    # Aliases explícitos primeiro.
    if q in _ASSET_ALIASES:
        return _ASSET_ALIASES[q], None

    # Tenta direto (às vezes o usuário já passa o id).
    direct = re.sub(r"\s+", "-", q).strip("-")
    if 2 <= len(direct) <= 60:
        # Não validamos aqui; o endpoint consumirá.
        candidate = direct
    else:
        candidate = q

    # Busca via /search
    params = {"query": q}
    data, err = _http_json(method="GET", url="https://api.coingecko.com/api/v3/search", params=params)
    if err:
        return None, err

    coins = (data or {}).get("coins") if isinstance(data, dict) else None
    if not isinstance(coins, list) or not coins:
        return None, "asset não encontrado"

    # Heurística simples de ranking.
    qn = _normalize(q)
    best_id: str | None = None
    best_score = -1
    for c in coins[:15]:
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id") or "").strip()
        name = str(c.get("name") or "").strip()
        sym = str(c.get("symbol") or "").strip()
        if not cid:
            continue

        score = 0
        if _normalize(cid) == qn or _normalize(name) == qn or _normalize(sym) == qn:
            score += 50
        if qn and qn in _normalize(name):
            score += 10
        if qn and qn in _normalize(cid):
            score += 8
        if qn and qn == _normalize(sym):
            score += 12

        if score > best_score:
            best_score = score
            best_id = cid

    return best_id or candidate, None


def _crypto_price(args: dict[str, Any]) -> ToolResult:
    asset_raw = str(args.get("asset", "") or "").strip().lower()
    if not asset_raw:
        return ToolResult(status="error", error="informe asset (ex: bitcoin|btc)")

    asset = _ASSET_ALIASES.get(asset_raw, asset_raw)
    vs_raw = str(args.get("vs", "brl,usd") or "brl,usd")
    vs = ",".join([v.strip().lower() for v in vs_raw.split(",") if v.strip()])
    if not vs:
        vs = "brl,usd"

    # Resolve id (para evitar falhas em assets fora do alias list).
    coin_id, id_err = _coingecko_find_coin_id(asset)
    if id_err:
        return ToolResult(status="error", error=id_err)
    assert coin_id is not None

    params = {"ids": coin_id, "vs_currencies": vs}
    data, err = _http_json(method="GET", url="https://api.coingecko.com/api/v3/simple/price", params=params)
    if err:
        return ToolResult(status="error", error=err)

    price = (data or {}).get(coin_id)
    if not isinstance(price, dict) or not price:
        return ToolResult(status="error", error="asset não encontrado")

    out = {"asset": asset_raw, "coin_id": coin_id, "vs": vs.split(","), "price": price}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _crypto_market_chart(args: dict[str, Any]) -> ToolResult:
    asset_raw = str(args.get("asset", "") or "").strip()
    if not asset_raw:
        return ToolResult(status="error", error="informe asset (ex: pi network|bitcoin|eth)")

    vs = str(args.get("vs", "usd") or "usd").strip().lower() or "usd"
    if vs not in {"usd", "brl", "eur"}:
        vs = "usd"

    days = str(args.get("days", "30") or "30").strip().lower() or "30"
    allowed_days = {"1", "7", "30", "90", "180", "365", "max"}
    if days not in allowed_days:
        # Aceita ints arbitrários também (CoinGecko permite números)
        try:
            di = int(days)
            if di < 1:
                di = 1
            if di > 3650:
                di = 3650
            days = str(di)
        except Exception:
            days = "30"

    coin_id, id_err = _coingecko_find_coin_id(asset_raw)
    if id_err:
        return ToolResult(status="error", error=id_err)
    assert coin_id is not None

    url = f"https://api.coingecko.com/api/v3/coins/{quote(coin_id)}/market_chart"
    params = {"vs_currency": vs, "days": days}
    data, err = _http_json(method="GET", url=url, params=params)
    if err:
        return ToolResult(status="error", error=err)

    prices = (data or {}).get("prices") if isinstance(data, dict) else None
    if not isinstance(prices, list) or len(prices) < 2:
        return ToolResult(status="error", error="sem dados de preços")

    series: list[tuple[float, float]] = []
    for p in prices:
        try:
            if isinstance(p, list) and len(p) >= 2:
                ts = float(p[0])
                val = float(p[1])
                series.append((ts, val))
        except Exception:
            continue

    if len(series) < 2:
        return ToolResult(status="error", error="sem dados válidos")

    vals = [v for _, v in series]
    first = vals[0]
    last = vals[-1]
    lo = min(vals)
    hi = max(vals)
    pct = None
    if first and first != 0.0:
        pct = (last - first) / first * 100.0

    # Métricas determinísticas (sem "prever" futuro): momentum, drawdown, volatilidade e razão de retornos positivos.
    # Observação: os pontos do CoinGecko podem ser sub-diários (ex.: horário), então tratamos como série temporal genérica.
    def _pct_change(a: float | None, b: float | None) -> float | None:
        try:
            if a is None or b is None or a == 0.0:
                return None
            return (b - a) / a * 100.0
        except Exception:
            return None

    def _find_value_at_or_before(target_ms: float) -> float | None:
        # Best-effort: encontra o último valor com timestamp <= target.
        try:
            for ts, v in reversed(series):
                if ts <= target_ms:
                    return float(v)
        except Exception:
            pass
        return None

    last_ts = series[-1][0]
    v_24h = _find_value_at_or_before(last_ts - 24.0 * 3600.0 * 1000.0)
    v_7d = _find_value_at_or_before(last_ts - 7.0 * 24.0 * 3600.0 * 1000.0)
    chg_24h = _pct_change(v_24h, last)
    chg_7d = _pct_change(v_7d, last)

    # Retornos simples e volatilidade (std dev em % por passo).
    returns_pct: list[float] = []
    pos_steps = 0
    neg_steps = 0
    for i in range(1, len(vals)):
        a = vals[i - 1]
        b = vals[i]
        if a == 0.0:
            continue
        r = (b - a) / a * 100.0
        returns_pct.append(r)
        if r > 0:
            pos_steps += 1
        elif r < 0:
            neg_steps += 1

    vol_step_pct: float | None = None
    if len(returns_pct) >= 2:
        try:
            mean = sum(returns_pct) / float(len(returns_pct))
            var = sum((x - mean) ** 2 for x in returns_pct) / float(len(returns_pct) - 1)
            vol_step_pct = var ** 0.5
        except Exception:
            vol_step_pct = None

    total_steps = max(1, pos_steps + neg_steps)
    pos_ratio = pos_steps / float(total_steps)

    # Max drawdown (pico->fundo) em %.
    max_dd: float | None = None
    try:
        peak = vals[0]
        max_dd_val = 0.0
        for v in vals:
            if v > peak:
                peak = v
            if peak > 0:
                dd = (v - peak) / peak * 100.0
                if dd < max_dd_val:
                    max_dd_val = dd
        max_dd = max_dd_val
    except Exception:
        max_dd = None

    # Tendência simples: compara média do início vs fim (últimos 20% dos pontos).
    trend: str = "lateral"
    try:
        n = len(vals)
        k = max(3, int(n * 0.2))
        early = vals[:k]
        late = vals[-k:]
        m1 = sum(early) / float(len(early))
        m2 = sum(late) / float(len(late))
        delta = _pct_change(m1, m2)
        if delta is not None:
            if delta > 1.5:
                trend = "alta"
            elif delta < -1.5:
                trend = "baixa"
            else:
                trend = "lateral"
    except Exception:
        trend = "lateral"

    # Texto enxuto (para o usuário) + payload estruturado (para automação).
    lines: list[str] = []
    lines.append(f"Asset: {asset_raw} (CoinGecko id: {coin_id})")
    lines.append(f"Período: {days}d | moeda: {vs.upper()} | pontos: {len(series)}")
    lines.append(f"Preço inicial: {first:.6g} | final: {last:.6g}")
    if pct is not None:
        lines.append(f"Variação no período: {pct:+.2f}%")
    if chg_24h is not None:
        lines.append(f"Mudança ~24h: {chg_24h:+.2f}%")
    if chg_7d is not None:
        lines.append(f"Mudança ~7d: {chg_7d:+.2f}%")
    lines.append(f"Mín: {lo:.6g} | Máx: {hi:.6g}")
    lines.append(f"Tendência (heurística): {trend}")
    if vol_step_pct is not None:
        lines.append(f"Volatilidade (por passo): ~{vol_step_pct:.3g}%")
    if max_dd is not None:
        lines.append(f"Max drawdown: {max_dd:.2f}%")
    lines.append(
        f"Proporção de passos positivos (histórico): {pos_ratio*100:.1f}% (isso NÃO é previsão)"
    )
    lines.append("Fonte: https://www.coingecko.com/")

    out = {
        "asset": asset_raw,
        "coin_id": coin_id,
        "vs": vs,
        "days": days,
        "points": len(series),
        "first": first,
        "last": last,
        "low": lo,
        "high": hi,
        "pct_change": pct,
        "change_24h_pct": chg_24h,
        "change_7d_pct": chg_7d,
        "trend": trend,
        "vol_step_pct": vol_step_pct,
        "max_drawdown_pct": max_dd,
        "pos_step_ratio": pos_ratio,
    }

    text = "\n".join(lines)
    # Inclui JSON compactado no final (útil para debug sem depender do LLM).
    text += "\n\nJSON:\n" + json.dumps(out, ensure_ascii=False)
    return ToolResult(status="ok", output=text)


def _arxiv_search(args: dict[str, Any]) -> ToolResult:
    query = str(args.get("query", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe query")

    try:
        max_results = int(args.get("max_results", 5) or 5)
    except Exception:
        max_results = 5
    if max_results < 1:
        max_results = 1
    if max_results > 10:
        max_results = 10

    # arXiv ATOM
    q = quote(query)
    url = f"https://export.arxiv.org/api/query?search_query=all:{q}&start=0&max_results={max_results}"

    try:
        u = httpx.URL(url)
        host = (u.host or "").lower()
        if u.scheme != "https" or host not in _ALLOWED_HOSTS:
            return ToolResult(status="error", error="host não permitido")

        with httpx.Client(timeout=12.0, follow_redirects=True) as client:
            resp = client.get(url)
        if resp.status_code >= 400:
            return ToolResult(status="error", error=f"HTTP {resp.status_code}: {resp.text[:200]}")

        import xml.etree.ElementTree as ET

        root = ET.fromstring(resp.text)
        ns = {"a": "http://www.w3.org/2005/Atom"}
        entries = root.findall("a:entry", ns)
        out_entries: list[dict[str, Any]] = []
        for e in entries[:max_results]:
            title = (e.findtext("a:title", default="", namespaces=ns) or "").strip()
            summary = (e.findtext("a:summary", default="", namespaces=ns) or "").strip()
            published = (e.findtext("a:published", default="", namespaces=ns) or "").strip()
            link = ""
            for l in e.findall("a:link", ns):
                href = l.attrib.get("href") or ""
                rel = (l.attrib.get("rel") or "").lower()
                if rel == "alternate" and href:
                    link = href
                    break
            authors = [
                (a.findtext("a:name", default="", namespaces=ns) or "").strip()
                for a in e.findall("a:author", ns)
            ]
            authors = [a for a in authors if a]
            out_entries.append(
                {
                    "title": title,
                    "published": published,
                    "url": link,
                    "authors": authors,
                    "summary": summary[:1200] + ("..." if len(summary) > 1200 else ""),
                }
            )

        out = {"query": query, "results": out_entries}
        return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        return ToolResult(status="error", error=str(exc))


def _tavily_search(args: dict[str, Any]) -> ToolResult:
    api_key = (os.getenv("OMNI_TAVILY_API_KEY") or "").strip()
    if not api_key:
        return ToolResult(status="error", error="OMNI_TAVILY_API_KEY não configurada")

    query = str(args.get("query", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe query")

    try:
        max_results = int(args.get("max_results", 5) or 5)
    except Exception:
        max_results = 5
    if max_results < 1:
        max_results = 1
    if max_results > 10:
        max_results = 10

    depth = str(args.get("depth", "basic") or "basic").strip().lower()
    if depth not in {"basic", "advanced"}:
        depth = "basic"

    body = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": depth,
        "include_answer": False,
        "include_images": False,
        "include_raw_content": False,
    }

    data, err = _http_json(method="POST", url="https://api.tavily.com/search", json_body=body)
    if err:
        return ToolResult(status="error", error=err)

    # Enxuga resultado.
    results = (data or {}).get("results") if isinstance(data, dict) else None
    slim: list[dict[str, Any]] = []
    if isinstance(results, list):
        for r in results[:max_results]:
            if not isinstance(r, dict):
                continue
            slim.append(
                {
                    "title": str(r.get("title", "") or "")[:160],
                    "url": str(r.get("url", "") or ""),
                    "content": str(r.get("content", "") or "")[:600],
                    "score": r.get("score"),
                }
            )

    out = {"query": query, "results": slim}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _geo_geocode(args: dict[str, Any]) -> ToolResult:
    query = str(args.get("query", "") or args.get("q", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe query")

    lang = str(args.get("lang", "pt") or "pt").strip().lower()
    if lang not in {"pt", "en"}:
        lang = "pt"

    country_codes = str(args.get("country_codes", "") or "").strip().lower()
    if country_codes and not re.fullmatch(r"[a-z]{2}(?:,[a-z]{2})*", country_codes):
        country_codes = ""

    params: dict[str, Any] = {
        "q": query,
        "format": "json",
        "limit": 3,
        "addressdetails": 1,
        "accept-language": lang,
    }
    if country_codes:
        params["countrycodes"] = country_codes

    data, err = _http_json(method="GET", url="https://nominatim.openstreetmap.org/search", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)

    if not isinstance(data, list) or not data:
        return ToolResult(status="error", error="nenhum resultado")

    slim: list[dict[str, Any]] = []
    for r in data[:3]:
        if not isinstance(r, dict):
            continue
        try:
            lat_raw = r.get("lat")
            lon_raw = r.get("lon")
            if lat_raw is None or lon_raw is None:
                continue
            lat = float(str(lat_raw).replace(",", "."))
            lon = float(str(lon_raw).replace(",", "."))
        except Exception:
            continue
        slim.append(
            {
                "display_name": str(r.get("display_name", "") or "")[:220],
                "lat": lat,
                "lon": lon,
                "type": r.get("type"),
                "class": r.get("class"),
                "address": r.get("address") or {},
            }
        )

    out = {"query": query, "results": slim}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _geo_reverse_geocode(args: dict[str, Any]) -> ToolResult:
    try:
        lat = float(str(args.get("lat", "")).replace(",", "."))
        lon = float(str(args.get("lon", "")).replace(",", "."))
    except Exception:
        return ToolResult(status="error", error="informe lat e lon")

    lang = str(args.get("lang", "pt") or "pt").strip().lower()
    if lang not in {"pt", "en"}:
        lang = "pt"

    params = {
        "lat": lat,
        "lon": lon,
        "format": "json",
        "addressdetails": 1,
        "accept-language": lang,
    }
    data, err = _http_json(method="GET", url="https://nominatim.openstreetmap.org/reverse", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)

    out = {
        "lat": lat,
        "lon": lon,
        "display_name": str((data or {}).get("display_name", "") or "")[:240],
        "address": (data or {}).get("address") or {},
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _geo_route_osrm(args: dict[str, Any]) -> ToolResult:
    origin = str(args.get("from", "") or args.get("origin", "") or "").strip()
    dest = str(args.get("to", "") or args.get("destination", "") or "").strip()
    if not origin or not dest:
        return ToolResult(status="error", error="informe from e to")

    profile = str(args.get("profile", "driving") or "driving").strip().lower()
    if profile not in {"driving", "walking", "cycling"}:
        profile = "driving"

    lang = str(args.get("lang", "pt") or "pt").strip().lower()
    if lang not in {"pt", "en"}:
        lang = "pt"

    # 1) Geocode origin/dest via Nominatim
    def _first_coord(q: str) -> tuple[float, float] | None:
        r, e = _http_json(
            method="GET",
            url="https://nominatim.openstreetmap.org/search",
            params={
                "q": q,
                "format": "json",
                "limit": 1,
                "addressdetails": 0,
                "accept-language": lang,
            },
            timeout_s=12.0,
        )
        if e or not isinstance(r, list) or not r:
            return None
        try:
            return float(r[0].get("lat")), float(r[0].get("lon"))
        except Exception:
            return None

    a = _first_coord(origin)
    b = _first_coord(dest)
    if a is None or b is None:
        return ToolResult(status="error", error="não consegui geocodificar origem/destino")

    lat1, lon1 = a
    lat2, lon2 = b

    # 2) Route via OSRM demo
    route_url = f"https://router.project-osrm.org/route/v1/{profile}/{lon1:.6f},{lat1:.6f};{lon2:.6f},{lat2:.6f}"
    params = {"overview": "false", "steps": "true", "annotations": "false"}
    data, err = _http_json(method="GET", url=route_url, params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)

    routes = (data or {}).get("routes") if isinstance(data, dict) else None
    if not isinstance(routes, list) or not routes:
        return ToolResult(status="error", error="sem rota")

    r0 = routes[0] or {}
    legs = r0.get("legs") if isinstance(r0, dict) else None
    steps: list[dict[str, Any]] = []
    if isinstance(legs, list) and legs:
        leg0 = legs[0] or {}
        for s in (leg0.get("steps") or [])[:18]:
            if not isinstance(s, dict):
                continue
            maneuver = s.get("maneuver") or {}
            steps.append(
                {
                    "name": str(s.get("name", "") or "")[:80],
                    "distance_m": s.get("distance"),
                    "duration_s": s.get("duration"),
                    "type": (maneuver.get("type") if isinstance(maneuver, dict) else None),
                    "modifier": (maneuver.get("modifier") if isinstance(maneuver, dict) else None),
                }
            )

    out = {
        "from": origin,
        "to": dest,
        "profile": profile,
        "origin": {"lat": lat1, "lon": lon1},
        "destination": {"lat": lat2, "lon": lon2},
        "distance_m": r0.get("distance"),
        "duration_s": r0.get("duration"),
        "steps": steps,
        "note": "OSRM demo + Nominatim têm rate-limit; use com moderação.",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _fx_convert(args: dict[str, Any]) -> ToolResult:
    try:
        amount = float(str(args.get("amount", "") or "").replace(",", "."))
    except Exception:
        return ToolResult(status="error", error="informe amount")

    cur_from = str(args.get("from", "") or args.get("base", "") or "").strip().upper()
    cur_to = str(args.get("to", "") or args.get("target", "") or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", cur_from) or not re.fullmatch(r"[A-Z]{3}", cur_to):
        return ToolResult(status="error", error="informe from/to como código de moeda (ex: USD, BRL)")

    params = {"amount": amount, "from": cur_from, "to": cur_to}
    data, err = _http_json(method="GET", url="https://api.frankfurter.app/latest", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)

    rates = (data or {}).get("rates") if isinstance(data, dict) else None
    out = {
        "amount": amount,
        "from": cur_from,
        "to": cur_to,
        "date": (data or {}).get("date") if isinstance(data, dict) else "",
        "result": (rates or {}).get(cur_to) if isinstance(rates, dict) else None,
        "provider": "frankfurter.app (ECB)",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _country_info(args: dict[str, Any]) -> ToolResult:
    query = str(args.get("name") or args.get("query") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe name (ou query)")

    # RestCountries: /v3.1/name/{name}?fullText=false
    safe = quote(query, safe="")
    fields = str(args.get("fields", "") or "").strip()
    params: dict[str, Any] = {}
    if fields:
        params["fields"] = fields

    data, err = _http_json(method="GET", url=f"https://restcountries.com/v3.1/name/{safe}", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)

    if not isinstance(data, list) or not data:
        return ToolResult(status="error", error="país não encontrado")

    c0 = data[0] or {}
    name = (((c0.get("name") or {}) if isinstance(c0, dict) else {}).get("common") or query)
    capital = (c0.get("capital") or []) if isinstance(c0, dict) else []
    out = {
        "query": query,
        "name": name,
        "cca2": c0.get("cca2") if isinstance(c0, dict) else None,
        "cca3": c0.get("cca3") if isinstance(c0, dict) else None,
        "capital": (capital[0] if isinstance(capital, list) and capital else ""),
        "region": c0.get("region") if isinstance(c0, dict) else None,
        "subregion": c0.get("subregion") if isinstance(c0, dict) else None,
        "population": c0.get("population") if isinstance(c0, dict) else None,
        "languages": c0.get("languages") if isinstance(c0, dict) else None,
        "currencies": c0.get("currencies") if isinstance(c0, dict) else None,
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _world_time(args: dict[str, Any]) -> ToolResult:
    tz = str(args.get("tz", "") or args.get("timezone", "") or "").strip()
    if not tz:
        return ToolResult(status="error", error="informe tz (ex: America/Sao_Paulo)")

    safe = quote(tz, safe="/+-_")
    data, err = _http_json(method="GET", url=f"https://worldtimeapi.org/api/timezone/{safe}", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)

    out = {
        "timezone": (data or {}).get("timezone") if isinstance(data, dict) else tz,
        "datetime": (data or {}).get("datetime") if isinstance(data, dict) else None,
        "utc_offset": (data or {}).get("utc_offset") if isinstance(data, dict) else None,
        "day_of_week": (data or {}).get("day_of_week") if isinstance(data, dict) else None,
        "week_number": (data or {}).get("week_number") if isinstance(data, dict) else None,
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _gdelt_search(args: dict[str, Any]) -> ToolResult:
    query = str(args.get("query", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe query")

    try:
        max_results = int(args.get("max_results", 5) or 5)
    except Exception:
        max_results = 5
    if max_results < 1:
        max_results = 1
    if max_results > 10:
        max_results = 10

    lang = str(args.get("lang", "") or "").strip()

    params: dict[str, Any] = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": max_results,
        "formatdatetime": "iso",
    }
    if lang:
        params["sourcelang"] = lang

    data, err = _http_json(method="GET", url="https://api.gdeltproject.org/api/v2/doc/doc", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)

    arts = (data or {}).get("articles") if isinstance(data, dict) else None
    slim: list[dict[str, Any]] = []
    if isinstance(arts, list):
        for a in arts[:max_results]:
            if not isinstance(a, dict):
                continue
            slim.append(
                {
                    "title": str(a.get("title", "") or "")[:220],
                    "url": str(a.get("url", "") or ""),
                    "sourceCountry": a.get("sourceCountry"),
                    "seendate": a.get("seendate"),
                }
            )

    out = {"query": query, "results": slim}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _openlibrary_search(args: dict[str, Any]) -> ToolResult:
    query = str(args.get("query", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe query")

    try:
        max_results = int(args.get("max_results", 5) or 5)
    except Exception:
        max_results = 5
    if max_results < 1:
        max_results = 1
    if max_results > 10:
        max_results = 10

    params = {"q": query, "limit": max_results}
    data, err = _http_json(method="GET", url="https://openlibrary.org/search.json", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)

    docs = (data or {}).get("docs") if isinstance(data, dict) else None
    slim: list[dict[str, Any]] = []
    if isinstance(docs, list):
        for d in docs[:max_results]:
            if not isinstance(d, dict):
                continue
            key = str(d.get("key", "") or "")
            slim.append(
                {
                    "title": str(d.get("title", "") or "")[:180],
                    "author": (d.get("author_name") or [""])[0] if isinstance(d.get("author_name"), list) else "",
                    "first_publish_year": d.get("first_publish_year"),
                    "url": ("https://openlibrary.org" + key) if key.startswith("/works/") else "",
                }
            )

    out = {"query": query, "results": slim}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _holidays(args: dict[str, Any]) -> ToolResult:
    try:
        year = int(args.get("year") or 0)
    except Exception:
        year = 0
    if year < 1900 or year > 2100:
        return ToolResult(status="error", error="informe year (ex: 2026)")

    cc = str(args.get("country_code", "") or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", cc):
        return ToolResult(status="error", error="informe country_code (ex: BR)")

    data, err = _http_json(method="GET", url=f"https://date.nager.at/api/v3/PublicHolidays/{year}/{cc}", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)

    if not isinstance(data, list):
        return ToolResult(status="error", error="resposta inesperada")

    slim: list[dict[str, Any]] = []
    for h in data[:40]:
        if not isinstance(h, dict):
            continue
        slim.append(
            {
                "date": h.get("date"),
                "localName": str(h.get("localName", "") or "")[:160],
                "name": str(h.get("name", "") or "")[:160],
                "types": h.get("types"),
            }
        )

    out = {"year": year, "country_code": cc, "holidays": slim}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _crossref_search(args: dict[str, Any]) -> ToolResult:
    query = str(args.get("query", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe query")

    try:
        rows = int(args.get("rows", 5) or 5)
    except Exception:
        rows = 5
    if rows < 1:
        rows = 1
    if rows > 10:
        rows = 10

    params = {"query": query, "rows": rows}
    data, err = _http_json(method="GET", url="https://api.crossref.org/works", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)

    msg = ((data or {}).get("message") or {}) if isinstance(data, dict) else {}
    items = msg.get("items") if isinstance(msg, dict) else None

    slim: list[dict[str, Any]] = []
    if isinstance(items, list):
        for it in items[:rows]:
            if not isinstance(it, dict):
                continue
            title = ""
            titles = it.get("title")
            if isinstance(titles, list) and titles:
                title = str(titles[0] or "")
            doi = str(it.get("DOI", "") or "")
            url = str(it.get("URL", "") or "")
            year = None
            try:
                issued = it.get("issued")
                parts = (((issued or {}).get("date-parts") or []) if isinstance(issued, dict) else [])
                if parts and isinstance(parts[0], list) and parts[0]:
                    year = parts[0][0]
            except Exception:
                year = None
            slim.append({"title": title[:240], "doi": doi, "url": url, "year": year})

    out = {"query": query, "rows": rows, "results": slim}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _fear_greed_index(args: dict[str, Any]) -> ToolResult:
    try:
        limit = int(args.get("limit", 1) or 1)
    except Exception:
        limit = 1
    if limit < 1:
        limit = 1
    if limit > 10:
        limit = 10

    params = {"limit": limit}
    data, err = _http_json(method="GET", url="https://api.alternative.me/fng/", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)

    rows = (data or {}).get("data") if isinstance(data, dict) else None
    slim: list[dict[str, Any]] = []
    if isinstance(rows, list):
        for r in rows[:limit]:
            if not isinstance(r, dict):
                continue
            slim.append(
                {
                    "value": r.get("value"),
                    "value_classification": r.get("value_classification"),
                    "timestamp": r.get("timestamp"),
                    "time_until_update": r.get("time_until_update"),
                }
            )

    out = {"provider": "alternative.me", "results": slim}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _earthquake_usgs(args: dict[str, Any]) -> ToolResult:
    try:
        days = int(args.get("days", 7) or 7)
    except Exception:
        days = 7
    if days < 1:
        days = 1
    if days > 30:
        days = 30

    try:
        min_mag = float(args.get("min_magnitude", 4.5) or 4.5)
    except Exception:
        min_mag = 4.5
    if min_mag < 0:
        min_mag = 0.0
    if min_mag > 9.9:
        min_mag = 9.9

    try:
        limit = int(args.get("limit", 10) or 10)
    except Exception:
        limit = 10
    if limit < 1:
        limit = 1
    if limit > 50:
        limit = 50

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    params: dict[str, Any] = {
        "format": "geojson",
        "starttime": start.date().isoformat(),
        "endtime": now.date().isoformat(),
        "minmagnitude": min_mag,
        "orderby": "time",
        "limit": limit,
    }

    data, err = _http_json(method="GET", url="https://earthquake.usgs.gov/fdsnws/event/1/query", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)

    feats = (data or {}).get("features") if isinstance(data, dict) else None
    slim: list[dict[str, Any]] = []
    if isinstance(feats, list):
        for f in feats[:limit]:
            if not isinstance(f, dict):
                continue
            props = f.get("properties") or {}
            geom = f.get("geometry") or {}
            coords = geom.get("coordinates") if isinstance(geom, dict) else None
            lon = lat = depth_km = None
            if isinstance(coords, list) and len(coords) >= 3:
                lon, lat, depth_km = coords[0], coords[1], coords[2]
            t_ms = props.get("time")
            when = None
            try:
                if isinstance(t_ms, (int, float)):
                    when = datetime.fromtimestamp(t_ms / 1000.0, tz=timezone.utc).isoformat()
            except Exception:
                when = None
            slim.append(
                {
                    "mag": props.get("mag"),
                    "place": str(props.get("place", "") or "")[:220],
                    "time_utc": when,
                    "url": props.get("url"),
                    "lat": lat,
                    "lon": lon,
                    "depth_km": depth_km,
                }
            )

    out = {
        "days": days,
        "min_magnitude": min_mag,
        "count": len(slim),
        "results": slim,
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _iss_position(args: dict[str, Any]) -> ToolResult:
    data, err = _http_json(method="GET", url="https://api.wheretheiss.at/v1/satellites/25544", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)

    out = {
        "name": (data or {}).get("name") if isinstance(data, dict) else "ISS",
        "latitude": (data or {}).get("latitude") if isinstance(data, dict) else None,
        "longitude": (data or {}).get("longitude") if isinstance(data, dict) else None,
        "altitude_km": (data or {}).get("altitude") if isinstance(data, dict) else None,
        "velocity_km_h": (data or {}).get("velocity") if isinstance(data, dict) else None,
        "visibility": (data or {}).get("visibility") if isinstance(data, dict) else None,
        "timestamp": (data or {}).get("timestamp") if isinstance(data, dict) else None,
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _covid_stats(args: dict[str, Any]) -> ToolResult:
    country = str(args.get("country", "") or "").strip()
    if country:
        safe = quote(country, safe="")
        url = f"https://disease.sh/v3/covid-19/countries/{safe}"
    else:
        url = "https://disease.sh/v3/covid-19/all"

    data, err = _http_json(method="GET", url=url, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)

    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    out = {
        "scope": (data.get("country") or "global") if country else "global",
        "updated": data.get("updated"),
        "cases": data.get("cases"),
        "todayCases": data.get("todayCases"),
        "deaths": data.get("deaths"),
        "todayDeaths": data.get("todayDeaths"),
        "recovered": data.get("recovered"),
        "todayRecovered": data.get("todayRecovered"),
        "active": data.get("active"),
        "critical": data.get("critical"),
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _openalex_works_search(args: dict[str, Any]) -> ToolResult:
    query = str(args.get("query", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe query")

    try:
        max_results = int(args.get("max_results", 5) or 5)
    except Exception:
        max_results = 5
    if max_results < 1:
        max_results = 1
    if max_results > 10:
        max_results = 10

    params = {
        "search": query,
        "per-page": max_results,
    }
    data, err = _http_json(method="GET", url="https://api.openalex.org/works", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)

    results = (data or {}).get("results") if isinstance(data, dict) else None
    slim: list[dict[str, Any]] = []
    if isinstance(results, list):
        for w in results[:max_results]:
            if not isinstance(w, dict):
                continue
            title = str(w.get("title", "") or "")
            doi = str((w.get("doi") or "") or "")
            host = (w.get("host_venue") or {}) if isinstance(w.get("host_venue"), dict) else {}
            slim.append(
                {
                    "id": w.get("id"),
                    "title": title[:240],
                    "year": w.get("publication_year"),
                    "cited_by_count": w.get("cited_by_count"),
                    "doi": doi,
                    "venue": host.get("display_name"),
                }
            )

    out = {"query": query, "results": slim}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _wikidata_search(args: dict[str, Any]) -> ToolResult:
    query = str(args.get("query", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe query")

    lang = str(args.get("lang", "pt") or "pt").strip().lower()
    if lang not in {"pt", "en"}:
        lang = "pt"

    try:
        limit = int(args.get("limit", 5) or 5)
    except Exception:
        limit = 5
    if limit < 1:
        limit = 1
    if limit > 10:
        limit = 10

    params = {
        "action": "wbsearchentities",
        "search": query,
        "language": lang,
        "format": "json",
        "limit": limit,
    }
    data, err = _http_json(method="GET", url="https://www.wikidata.org/w/api.php", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)

    rows = (data or {}).get("search") if isinstance(data, dict) else None
    slim: list[dict[str, Any]] = []
    if isinstance(rows, list):
        for r in rows[:limit]:
            if not isinstance(r, dict):
                continue
            qid = str(r.get("id", "") or "")
            slim.append(
                {
                    "id": qid,
                    "label": r.get("label"),
                    "description": r.get("description"),
                    "url": (f"https://www.wikidata.org/wiki/{qid}" if qid else ""),
                }
            )

    out = {"query": query, "lang": lang, "results": slim}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _wikidata_entity(args: dict[str, Any]) -> ToolResult:
    entity_id = str(args.get("id", "") or "").strip().upper()
    if not re.fullmatch(r"[PQ]\d+", entity_id):
        return ToolResult(status="error", error="informe id (ex: Q42)")

    data, err = _http_json(method="GET", url=f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)

    # Enxuga: tenta pegar label/description e claims count.
    ent = (((data or {}).get("entities") or {}) if isinstance(data, dict) else {}).get(entity_id) if isinstance(data, dict) else None
    labels = (ent.get("labels") or {}) if isinstance(ent, dict) else {}
    descs = (ent.get("descriptions") or {}) if isinstance(ent, dict) else {}
    claims = (ent.get("claims") or {}) if isinstance(ent, dict) else {}

    def _pick_lang(d: dict[str, Any]) -> str:
        for k in ("pt", "en"):
            if k in d and isinstance(d.get(k), dict) and (d.get(k) or {}).get("value"):
                return str((d.get(k) or {}).get("value") or "")
        # fallback
        for v in d.values():
            if isinstance(v, dict) and v.get("value"):
                return str(v.get("value") or "")
        return ""

    out = {
        "id": entity_id,
        "url": f"https://www.wikidata.org/wiki/{entity_id}",
        "label": _pick_lang(labels),
        "description": _pick_lang(descs),
        "claims_count": (len(claims) if isinstance(claims, dict) else None),
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _worldbank_indicator(args: dict[str, Any]) -> ToolResult:
    cc = str(args.get("country_code", "") or "").strip().upper()
    indicator = str(args.get("indicator", "") or "").strip()
    if not re.fullmatch(r"[A-Z]{2,3}", cc):
        return ToolResult(status="error", error="informe country_code (ex: BR)")
    if not re.fullmatch(r"[A-Z0-9_\.]{3,40}", indicator):
        return ToolResult(status="error", error="informe indicator (ex: SP.POP.TOTL)")

    date = str(args.get("date", "") or "").strip()
    params: dict[str, Any] = {
        "format": "json",
        "per_page": 60,
    }
    if date:
        params["date"] = date

    url = f"https://api.worldbank.org/v2/country/{cc}/indicator/{indicator}"
    data, err = _http_json(method="GET", url=url, params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)

    # Resposta típica: [meta, [rows...]]
    rows = None
    if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list):
        rows = data[1]

    if not isinstance(rows, list) or not rows:
        return ToolResult(status="error", error="sem dados")

    # Pega o primeiro valor não-nulo (mais recente vem primeiro).
    pick = None
    for r in rows:
        if not isinstance(r, dict):
            continue
        if r.get("value") is not None:
            pick = r
            break

    if not isinstance(pick, dict):
        return ToolResult(status="error", error="sem valores não-nulos")

    out = {
        "country_code": cc,
        "indicator": indicator,
        "date": pick.get("date"),
        "value": pick.get("value"),
        "country": (pick.get("country") or {}).get("value") if isinstance(pick.get("country"), dict) else None,
        "indicator_name": (pick.get("indicator") or {}).get("value") if isinstance(pick.get("indicator"), dict) else None,
        "source": "api.worldbank.org",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _hackernews_front_page(args: dict[str, Any]) -> ToolResult:
    try:
        limit = int(args.get("limit", 10) or 10)
    except Exception:
        limit = 10
    if limit < 1:
        limit = 1
    if limit > 20:
        limit = 20

    # Algolia HN API: front page
    params = {"tags": "front_page", "hitsPerPage": limit}
    data, err = _http_json(method="GET", url="https://hn.algolia.com/api/v1/search", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)

    hits = (data or {}).get("hits") if isinstance(data, dict) else None
    slim: list[dict[str, Any]] = []
    if isinstance(hits, list):
        for h in hits[:limit]:
            if not isinstance(h, dict):
                continue
            slim.append(
                {
                    "title": str(h.get("title", "") or "")[:240],
                    "url": h.get("url") or h.get("story_url") or "",
                    "points": h.get("points"),
                    "author": h.get("author"),
                    "created_at": h.get("created_at"),
                    "hn_id": h.get("objectID"),
                }
            )

    out = {"source": "hn.algolia.com", "results": slim}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _github_repo_search(args: dict[str, Any]) -> ToolResult:
    query = str(args.get("query", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe query")

    try:
        limit = int(args.get("limit", 5) or 5)
    except Exception:
        limit = 5
    if limit < 1:
        limit = 1
    if limit > 10:
        limit = 10

    params = {"q": query, "per_page": limit, "sort": "stars", "order": "desc"}
    data, err = _http_json(method="GET", url="https://api.github.com/search/repositories", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)

    items = (data or {}).get("items") if isinstance(data, dict) else None
    slim: list[dict[str, Any]] = []
    if isinstance(items, list):
        for it in items[:limit]:
            if not isinstance(it, dict):
                continue
            slim.append(
                {
                    "full_name": it.get("full_name"),
                    "description": str(it.get("description", "") or "")[:280],
                    "stars": it.get("stargazers_count"),
                    "language": it.get("language"),
                    "url": it.get("html_url"),
                }
            )

    out = {"query": query, "results": slim}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _stackexchange_search(args: dict[str, Any]) -> ToolResult:
    query = str(args.get("query", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe query")

    try:
        limit = int(args.get("limit", 5) or 5)
    except Exception:
        limit = 5
    if limit < 1:
        limit = 1
    if limit > 10:
        limit = 10

    params = {
        "order": "desc",
        "sort": "relevance",
        "q": query,
        "site": "stackoverflow",
        "pagesize": limit,
        "filter": "default",
    }
    data, err = _http_json(method="GET", url="https://api.stackexchange.com/2.3/search/advanced", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)

    items = (data or {}).get("items") if isinstance(data, dict) else None
    slim: list[dict[str, Any]] = []
    if isinstance(items, list):
        for it in items[:limit]:
            if not isinstance(it, dict):
                continue
            slim.append(
                {
                    "title": str(it.get("title", "") or "")[:240],
                    "link": it.get("link"),
                    "score": it.get("score"),
                    "answer_count": it.get("answer_count"),
                    "is_answered": it.get("is_answered"),
                }
            )

    out = {"query": query, "site": "stackoverflow", "results": slim}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _dictionary_define(args: dict[str, Any]) -> ToolResult:
    term = str(args.get("term", "") or "").strip()
    if not term:
        return ToolResult(status="error", error="informe term")

    lang = str(args.get("lang", "en") or "en").strip().lower()
    if not re.fullmatch(r"[a-z]{2,5}", lang):
        lang = "en"

    safe = quote(term, safe="")
    data, err = _http_json(method="GET", url=f"https://api.dictionaryapi.dev/api/v2/entries/{lang}/{safe}", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)

    if not isinstance(data, list) or not data:
        return ToolResult(status="error", error="sem resultados")

    first = data[0] if isinstance(data[0], dict) else {}
    meanings = first.get("meanings") if isinstance(first, dict) else None
    slim_meanings: list[dict[str, Any]] = []
    if isinstance(meanings, list):
        for m in meanings[:4]:
            if not isinstance(m, dict):
                continue
            defs = m.get("definitions")
            dslim = []
            if isinstance(defs, list):
                for d in defs[:3]:
                    if not isinstance(d, dict):
                        continue
                    dslim.append({"definition": str(d.get("definition", "") or "")[:420], "example": str(d.get("example", "") or "")[:220]})
            slim_meanings.append({"partOfSpeech": m.get("partOfSpeech"), "definitions": dslim})

    out = {
        "term": first.get("word") if isinstance(first, dict) else term,
        "phonetic": (first.get("phonetic") if isinstance(first, dict) else None),
        "meanings": slim_meanings,
        "source": "dictionaryapi.dev",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _lyrics(args: dict[str, Any]) -> ToolResult:
    artist = str(args.get("artist", "") or "").strip()
    title = str(args.get("title", "") or "").strip()
    if not artist or not title:
        return ToolResult(status="error", error="informe artist e title")

    a = quote(artist, safe="")
    t = quote(title, safe="")
    data, err = _http_json(method="GET", url=f"https://api.lyrics.ovh/v1/{a}/{t}", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    lyr = str(data.get("lyrics", "") or "").strip()
    if not lyr:
        return ToolResult(status="error", error="letra não encontrada")

    out = {"artist": artist, "title": title, "lyrics": lyr[:5000] + ("..." if len(lyr) > 5000 else "")}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _joke(args: dict[str, Any]) -> ToolResult:
    data, err = _http_json(method="GET", url="https://official-joke-api.appspot.com/random_joke", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")
    out = {"type": data.get("type"), "setup": str(data.get("setup", "") or "")[:500], "punchline": str(data.get("punchline", "") or "")[:500]}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _trivia(args: dict[str, Any]) -> ToolResult:
    try:
        amount = int(args.get("amount", 5) or 5)
    except Exception:
        amount = 5
    if amount < 1:
        amount = 1
    if amount > 10:
        amount = 10

    difficulty = str(args.get("difficulty", "") or "").strip().lower()
    if difficulty and difficulty not in {"easy", "medium", "hard"}:
        difficulty = ""
    qtype = str(args.get("type", "multiple") or "multiple").strip().lower()
    if qtype not in {"multiple", "boolean"}:
        qtype = "multiple"

    params: dict[str, Any] = {"amount": amount, "type": qtype}
    if difficulty:
        params["difficulty"] = difficulty

    data, err = _http_json(method="GET", url="https://opentdb.com/api.php", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    results = data.get("results")
    slim: list[dict[str, Any]] = []
    if isinstance(results, list):
        for r in results[:amount]:
            if not isinstance(r, dict):
                continue
            slim.append(
                {
                    "category": r.get("category"),
                    "difficulty": r.get("difficulty"),
                    "type": r.get("type"),
                    "question": r.get("question"),
                    "correct_answer": r.get("correct_answer"),
                    "incorrect_answers": r.get("incorrect_answers"),
                }
            )

    out = {"amount": amount, "results": slim, "source": "opentdb.com"}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _pokemon_info(args: dict[str, Any]) -> ToolResult:
    name_or_id = str(args.get("name_or_id", "") or "").strip().lower()
    if not name_or_id:
        return ToolResult(status="error", error="informe name_or_id")

    safe = quote(name_or_id, safe="")
    data, err = _http_json(method="GET", url=f"https://pokeapi.co/api/v2/pokemon/{safe}", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    types = []
    for t in (data.get("types") or []):
        if isinstance(t, dict) and isinstance(t.get("type"), dict):
            types.append((t.get("type") or {}).get("name"))

    stats = {}
    for s in (data.get("stats") or []):
        if not isinstance(s, dict) or not isinstance(s.get("stat"), dict):
            continue
        k = (s.get("stat") or {}).get("name")
        if k:
            stats[str(k)] = s.get("base_stat")

    out = {
        "id": data.get("id"),
        "name": data.get("name"),
        "types": [t for t in types if t],
        "height": data.get("height"),
        "weight": data.get("weight"),
        "stats": stats,
        "source": "pokeapi.co",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _ip_info(args: dict[str, Any]) -> ToolResult:
    ip = str(args.get("ip", "") or "").strip()
    if ip and not re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", ip):
        return ToolResult(status="error", error="ip inválido (use IPv4) ou deixe vazio")

    url = "https://ipapi.co/json/" if not ip else f"https://ipapi.co/{quote(ip, safe='')}/json/"
    data, err = _http_json(method="GET", url=url, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    out = {
        "ip": data.get("ip"),
        "city": data.get("city"),
        "region": data.get("region"),
        "country": data.get("country_name") or data.get("country"),
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "org": data.get("org"),
        "timezone": data.get("timezone"),
        "source": "ipapi.co",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _random_user(args: dict[str, Any]) -> ToolResult:
    nat = str(args.get("nat", "") or "").strip().upper()
    gender = str(args.get("gender", "") or "").strip().lower()
    params: dict[str, Any] = {"results": 1}
    if nat and re.fullmatch(r"[A-Z]{2}", nat):
        params["nat"] = nat.lower()
    if gender in {"male", "female"}:
        params["gender"] = gender

    data, err = _http_json(method="GET", url="https://randomuser.me/api/", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    results = data.get("results")
    if not isinstance(results, list) or not results or not isinstance(results[0], dict):
        return ToolResult(status="error", error="sem resultados")

    r0 = results[0]
    name_raw = r0.get("name")
    name: dict[str, Any] = cast(dict[str, Any], name_raw) if isinstance(name_raw, dict) else {}
    loc_raw = r0.get("location")
    loc: dict[str, Any] = cast(dict[str, Any], loc_raw) if isinstance(loc_raw, dict) else {}
    login_raw = r0.get("login")
    picture_raw = r0.get("picture")
    out = {
        "name": " ".join([str(name.get("first", "") or "").strip(), str(name.get("last", "") or "").strip()]).strip(),
        "email": r0.get("email"),
        "phone": r0.get("phone"),
        "country": loc.get("country"),
        "city": loc.get("city"),
        "username": (login_raw.get("username") if isinstance(login_raw, dict) else None),
        "picture": (picture_raw.get("large") if isinstance(picture_raw, dict) else None),
        "source": "randomuser.me",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _cat_fact(args: dict[str, Any]) -> ToolResult:
    data, err = _http_json(method="GET", url="https://catfact.ninja/fact", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")
    out = {"fact": str(data.get("fact", "") or "")[:600], "length": data.get("length"), "source": "catfact.ninja"}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _qr_code_url(args: dict[str, Any]) -> ToolResult:
    payload = str(args.get("data", "") or "").strip()
    if not payload:
        return ToolResult(status="error", error="informe data")

    size = str(args.get("size", "200x200") or "200x200").strip().lower()
    if not re.fullmatch(r"\d{2,4}x\d{2,4}", size):
        size = "200x200"

    # Não baixa a imagem; apenas retorna a URL pronta.
    url = f"https://api.qrserver.com/v1/create-qr-code/?size={quote(size, safe='')}&data={quote(payload, safe='')}"
    out = {"data": payload, "size": size, "url": url, "source": "api.qrserver.com"}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _osv_vuln(args: dict[str, Any]) -> ToolResult:
    vuln_id = str(args.get("id", "") or "").strip()
    if not vuln_id or not re.fullmatch(r"[A-Za-z0-9\-\.]{6,80}", vuln_id):
        return ToolResult(status="error", error="informe id (ex: GHSA-... | OSV-... | CVE-...)")

    safe = quote(vuln_id, safe="")
    data, err = _http_json(method="GET", url=f"https://api.osv.dev/v1/vulns/{safe}", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    refs = data.get("references")
    slim_refs: list[dict[str, Any]] = []
    if isinstance(refs, list):
        for r in refs[:10]:
            if not isinstance(r, dict):
                continue
            slim_refs.append({"type": r.get("type"), "url": r.get("url")})

    severities = data.get("severity")
    slim_sev: list[dict[str, Any]] = []
    if isinstance(severities, list):
        for s in severities[:6]:
            if not isinstance(s, dict):
                continue
            slim_sev.append({"type": s.get("type"), "score": s.get("score")})

    details = str(data.get("details", "") or "").strip()
    out = {
        "id": data.get("id") or vuln_id,
        "summary": str(data.get("summary", "") or "")[:360],
        "published": data.get("published"),
        "modified": data.get("modified"),
        "aliases": data.get("aliases") if isinstance(data.get("aliases"), list) else [],
        "severity": slim_sev,
        "references": slim_refs,
        "details": details[:2000] + ("..." if len(details) > 2000 else ""),
        "source": "api.osv.dev",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


_OSV_ECOSYSTEM_ALIASES = {
    "pypi": "PyPI",
    "pip": "PyPI",
    "python": "PyPI",
    "npm": "npm",
    "node": "npm",
    "nodejs": "npm",
    "crates": "crates.io",
    "crates.io": "crates.io",
    "rust": "crates.io",
    "rubygems": "RubyGems",
    "maven": "Maven",
    "nuget": "NuGet",
    "go": "Go",
}


def _osv_query(args: dict[str, Any]) -> ToolResult:
    ecosystem_raw = str(args.get("ecosystem", "") or "").strip()
    name = str(args.get("name", "") or "").strip()
    version = str(args.get("version", "") or "").strip()
    if not ecosystem_raw or not name or not version:
        return ToolResult(status="error", error="informe ecosystem, name e version")

    # OSV é case-sensitive; normalizamos aliases comuns.
    eco_key = ecosystem_raw.strip().lower()
    ecosystem = _OSV_ECOSYSTEM_ALIASES.get(eco_key, ecosystem_raw)

    try:
        limit = int(args.get("limit", 10) or 10)
    except Exception:
        limit = 10
    if limit < 1:
        limit = 1
    if limit > 50:
        limit = 50

    body = {
        "package": {"name": name, "ecosystem": ecosystem},
        "version": version,
    }
    data, err = _http_json(method="POST", url="https://api.osv.dev/v1/query", json_body=body, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)

    vulns = (data or {}).get("vulns") if isinstance(data, dict) else None
    slim: list[dict[str, Any]] = []
    if isinstance(vulns, list):
        for v in vulns[:limit]:
            if not isinstance(v, dict):
                continue
            slim.append(
                {
                    "id": v.get("id"),
                    "summary": str(v.get("summary", "") or "")[:260],
                    "published": v.get("published"),
                    "modified": v.get("modified"),
                    "aliases": v.get("aliases") if isinstance(v.get("aliases"), list) else [],
                }
            )

    out = {
        "package": {"ecosystem": ecosystem, "name": name, "version": version},
        "count": len(slim),
        "results": slim,
        "source": "api.osv.dev",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _pypi_project(args: dict[str, Any]) -> ToolResult:
    name = str(args.get("name", "") or "").strip()
    if not name or not re.fullmatch(r"[A-Za-z0-9_.\-]{1,80}", name):
        return ToolResult(status="error", error="informe name (ex: requests)")

    safe = quote(name, safe="")
    data, err = _http_json(method="GET", url=f"https://pypi.org/pypi/{safe}/json", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    info_raw = data.get("info")
    info: dict[str, Any] = cast(dict[str, Any], info_raw) if isinstance(info_raw, dict) else {}
    urls_raw = info.get("project_urls")
    urls: dict[str, Any] = cast(dict[str, Any], urls_raw) if isinstance(urls_raw, dict) else {}

    out = {
        "name": info.get("name") or name,
        "version": info.get("version"),
        "summary": str(info.get("summary", "") or "")[:320],
        "license": info.get("license"),
        "home_page": info.get("home_page"),
        "project_urls": {k: urls.get(k) for k in list(urls.keys())[:10]},
        "requires_python": info.get("requires_python"),
        "source": "pypi.org",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _npm_package(args: dict[str, Any]) -> ToolResult:
    name = str(args.get("name", "") or "").strip()
    if not name:
        return ToolResult(status="error", error="informe name (ex: express ou @scope/name)")
    # valida permissivo (escopo + /) e evita espaços
    if re.search(r"\s", name) or len(name) > 160:
        return ToolResult(status="error", error="name inválido")

    safe = quote(name, safe="")
    data, err = _http_json(method="GET", url=f"https://registry.npmjs.org/{safe}/latest", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    kw = data.get("keywords")
    out = {
        "name": data.get("name") or name,
        "version": data.get("version"),
        "description": str(data.get("description", "") or "")[:320],
        "license": data.get("license"),
        "homepage": data.get("homepage"),
        "repository": (data.get("repository") or {}).get("url") if isinstance(data.get("repository"), dict) else data.get("repository"),
        "keywords": (kw[:15] if isinstance(kw, list) else []),
        "source": "registry.npmjs.org",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _cratesio_crate(args: dict[str, Any]) -> ToolResult:
    name = str(args.get("name", "") or "").strip()
    if not name or not re.fullmatch(r"[A-Za-z0-9_\-]{1,64}", name):
        return ToolResult(status="error", error="informe name (ex: tokio)")

    safe = quote(name, safe="")
    data, err = _http_json(method="GET", url=f"https://crates.io/api/v1/crates/{safe}", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    crate_raw = data.get("crate")
    crate: dict[str, Any] = cast(dict[str, Any], crate_raw) if isinstance(crate_raw, dict) else {}
    out = {
        "name": crate.get("id") or name,
        "version": crate.get("newest_version"),
        "description": str(crate.get("description", "") or "")[:320],
        "downloads": crate.get("downloads"),
        "homepage": crate.get("homepage"),
        "repository": crate.get("repository"),
        "documentation": crate.get("documentation"),
        "source": "crates.io",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _dns_google_resolve(args: dict[str, Any]) -> ToolResult:
    name = str(args.get("name", "") or "").strip().rstrip(".")
    if not name or len(name) > 253 or re.search(r"\s", name):
        return ToolResult(status="error", error="informe name (ex: example.com)")

    rtype = str(args.get("type", "A") or "A").strip().upper()
    if rtype not in {"A", "AAAA", "CNAME", "MX", "TXT"}:
        rtype = "A"

    params = {"name": name, "type": rtype}
    data, err = _http_json(method="GET", url="https://dns.google/resolve", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    answers = data.get("Answer")
    slim: list[dict[str, Any]] = []
    if isinstance(answers, list):
        for a in answers[:20]:
            if not isinstance(a, dict):
                continue
            slim.append({"name": a.get("name"), "type": a.get("type"), "ttl": a.get("TTL"), "data": a.get("data")})

    out = {
        "name": name,
        "type": rtype,
        "status": data.get("Status"),
        "answers": slim,
        "source": "dns.google",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _github_status(args: dict[str, Any]) -> ToolResult:
    data, err = _http_json(method="GET", url="https://www.githubstatus.com/api/v2/status.json", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    page_raw = data.get("page")
    page: dict[str, Any] = cast(dict[str, Any], page_raw) if isinstance(page_raw, dict) else {}
    status_raw = data.get("status")
    status: dict[str, Any] = cast(dict[str, Any], status_raw) if isinstance(status_raw, dict) else {}
    out = {
        "indicator": status.get("indicator"),
        "description": status.get("description"),
        "page": {"name": page.get("name"), "url": page.get("url")},
        "source": "www.githubstatus.com",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _rdap_domain(args: dict[str, Any]) -> ToolResult:
    domain = str(args.get("domain", "") or "").strip().lower().rstrip(".")
    if not domain or len(domain) > 253 or re.search(r"\s", domain):
        return ToolResult(status="error", error="informe domain (ex: example.com)")
    if not re.search(r"\.", domain):
        return ToolResult(status="error", error="domain inválido")

    data, err = _http_json(method="GET", url=f"https://rdap.org/domain/{quote(domain, safe='')}", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    events = data.get("events")
    slim_events: list[dict[str, Any]] = []
    if isinstance(events, list):
        for e in events[:10]:
            if not isinstance(e, dict):
                continue
            slim_events.append({"eventAction": e.get("eventAction"), "eventDate": e.get("eventDate")})

    links = data.get("links")
    out = {
        "objectClassName": data.get("objectClassName"),
        "ldhName": data.get("ldhName"),
        "unicodeName": data.get("unicodeName"),
        "handle": data.get("handle"),
        "status": data.get("status") if isinstance(data.get("status"), list) else [],
        "events": slim_events,
        "links": (links[:6] if isinstance(links, list) else []),
        "source": "rdap.org",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _rdap_ip(args: dict[str, Any]) -> ToolResult:
    ip = str(args.get("ip", "") or "").strip()
    if not ip or not re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", ip):
        return ToolResult(status="error", error="informe ip (IPv4)")

    data, err = _http_json(method="GET", url=f"https://rdap.org/ip/{quote(ip, safe='')}", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    out = {
        "objectClassName": data.get("objectClassName"),
        "handle": data.get("handle"),
        "name": data.get("name"),
        "type": data.get("type"),
        "startAddress": data.get("startAddress"),
        "endAddress": data.get("endAddress"),
        "ipVersion": data.get("ipVersion"),
        "country": data.get("country"),
        "status": data.get("status") if isinstance(data.get("status"), list) else [],
        "source": "rdap.org",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _bgpview_ip(args: dict[str, Any]) -> ToolResult:
    ip = str(args.get("ip", "") or "").strip()
    if not ip or not re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", ip):
        return ToolResult(status="error", error="informe ip (IPv4)")

    data, err = _http_json(method="GET", url=f"https://api.bgpview.io/ip/{quote(ip, safe='')}", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    d_raw = data.get("data")
    d: dict[str, Any] = cast(dict[str, Any], d_raw) if isinstance(d_raw, dict) else {}
    asn_raw = d.get("asn")
    asn: dict[str, Any] = cast(dict[str, Any], asn_raw) if isinstance(asn_raw, dict) else {}
    prefixes = d.get("prefixes")
    out = {
        "ip": ip,
        "asn": {
            "asn": asn.get("asn"),
            "name": asn.get("name"),
            "description": asn.get("description"),
            "country_code": asn.get("country_code"),
        },
        "prefixes": (prefixes[:6] if isinstance(prefixes, list) else []),
        "source": "api.bgpview.io",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _bgpview_asn(args: dict[str, Any]) -> ToolResult:
    asn_raw = str(args.get("asn", "") or "").strip().upper().lstrip("AS")
    if not asn_raw or not re.fullmatch(r"\d{1,10}", asn_raw):
        return ToolResult(status="error", error="informe asn (ex: 15169)")

    data, err = _http_json(method="GET", url=f"https://api.bgpview.io/asn/{quote(asn_raw, safe='')}", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    d_raw = data.get("data")
    d: dict[str, Any] = cast(dict[str, Any], d_raw) if isinstance(d_raw, dict) else {}
    email_contacts_raw = d.get("email_contacts")
    email_contacts = email_contacts_raw[:10] if isinstance(email_contacts_raw, list) else []
    out = {
        "asn": d.get("asn"),
        "name": d.get("name"),
        "description": str(d.get("description", "") or "")[:320],
        "country_code": d.get("country_code"),
        "website": d.get("website"),
        "email_contacts": email_contacts,
        "source": "api.bgpview.io",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _crtsh_search(args: dict[str, Any]) -> ToolResult:
    query = str(args.get("query", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe query")

    try:
        limit = int(args.get("limit", 10) or 10)
    except Exception:
        limit = 10
    if limit < 1:
        limit = 1
    if limit > 25:
        limit = 25

    # crt.sh JSON output
    params = {"q": query, "output": "json"}
    data, err = _http_json(method="GET", url="https://crt.sh/", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)

    if not isinstance(data, list):
        return ToolResult(status="error", error="resposta inesperada")

    slim: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for r in data:
        if not isinstance(r, dict):
            continue
        rid = str(r.get("id", "") or "")
        if rid and rid in seen_ids:
            continue
        if rid:
            seen_ids.add(rid)
        slim.append(
            {
                "id": r.get("id"),
                "common_name": r.get("common_name"),
                "name_value": str(r.get("name_value", "") or "")[:220],
                "issuer_name": str(r.get("issuer_name", "") or "")[:220],
                "not_before": r.get("not_before"),
                "not_after": r.get("not_after"),
            }
        )
        if len(slim) >= limit:
            break

    out = {"query": query, "count": len(slim), "results": slim, "source": "crt.sh"}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _cisa_kev_search(args: dict[str, Any]) -> ToolResult:
    query = str(args.get("query", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe query")

    try:
        limit = int(args.get("limit", 10) or 10)
    except Exception:
        limit = 10
    if limit < 1:
        limit = 1
    if limit > 30:
        limit = 30

    data, err = _http_json(
        method="GET",
        url="https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
        timeout_s=12.0,
    )
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    vulns = data.get("vulnerabilities")
    if not isinstance(vulns, list):
        return ToolResult(status="error", error="sem dados")

    qn = _normalize(query)
    slim: list[dict[str, Any]] = []
    for v in vulns:
        if not isinstance(v, dict):
            continue
        hay = " ".join(
            [
                str(v.get("cveID", "") or ""),
                str(v.get("vendorProject", "") or ""),
                str(v.get("product", "") or ""),
                str(v.get("vulnerabilityName", "") or ""),
                str(v.get("shortDescription", "") or ""),
            ]
        )
        if qn in _normalize(hay):
            slim.append(
                {
                    "cve": v.get("cveID"),
                    "vendor": v.get("vendorProject"),
                    "product": v.get("product"),
                    "name": str(v.get("vulnerabilityName", "") or "")[:200],
                    "addedDate": v.get("dateAdded"),
                    "dueDate": v.get("dueDate"),
                    "requiredAction": str(v.get("requiredAction", "") or "")[:240],
                }
            )
            if len(slim) >= limit:
                break

    out = {"query": query, "count": len(slim), "results": slim, "source": "www.cisa.gov"}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _cloudflare_status(args: dict[str, Any]) -> ToolResult:
    data, err = _http_json(method="GET", url="https://www.cloudflarestatus.com/api/v2/status.json", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    page_raw = data.get("page")
    page: dict[str, Any] = cast(dict[str, Any], page_raw) if isinstance(page_raw, dict) else {}
    status_raw = data.get("status")
    status: dict[str, Any] = cast(dict[str, Any], status_raw) if isinstance(status_raw, dict) else {}
    out = {
        "indicator": status.get("indicator"),
        "description": status.get("description"),
        "page": {"name": page.get("name"), "url": page.get("url")},
        "source": "www.cloudflarestatus.com",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _discord_status(args: dict[str, Any]) -> ToolResult:
    data, err = _http_json(method="GET", url="https://discordstatus.com/api/v2/status.json", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    page_raw = data.get("page")
    page: dict[str, Any] = cast(dict[str, Any], page_raw) if isinstance(page_raw, dict) else {}
    status_raw = data.get("status")
    status: dict[str, Any] = cast(dict[str, Any], status_raw) if isinstance(status_raw, dict) else {}
    out = {
        "indicator": status.get("indicator"),
        "description": status.get("description"),
        "page": {"name": page.get("name"), "url": page.get("url")},
        "source": "discordstatus.com",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _ripestat_ip(args: dict[str, Any]) -> ToolResult:
    ip = str(args.get("ip", "") or "").strip()
    if not ip or not re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", ip):
        return ToolResult(status="error", error="informe ip (IPv4)")

    params = {"resource": ip}
    data, err = _http_json(method="GET", url="https://stat.ripe.net/data/network-info/data.json", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    d_raw = data.get("data")
    d: dict[str, Any] = cast(dict[str, Any], d_raw) if isinstance(d_raw, dict) else {}
    out = {
        "resource": ip,
        "prefix": d.get("prefix"),
        "asn": d.get("asn"),
        "holder": d.get("holder"),
        "block": {
            "resource": (d.get("resource") if isinstance(d.get("resource"), str) else None),
            "start": d.get("start"),
            "end": d.get("end"),
        },
        "source": "stat.ripe.net",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _ripestat_asn(args: dict[str, Any]) -> ToolResult:
    asn_raw = str(args.get("asn", "") or "").strip().upper().lstrip("AS")
    if not asn_raw or not re.fullmatch(r"\d{1,10}", asn_raw):
        return ToolResult(status="error", error="informe asn (ex: 15169)")

    params = {"resource": f"AS{asn_raw}"}
    data, err = _http_json(method="GET", url="https://stat.ripe.net/data/as-overview/data.json", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    d_raw = data.get("data")
    d: dict[str, Any] = cast(dict[str, Any], d_raw) if isinstance(d_raw, dict) else {}

    # Mantém saída pequena; alguns campos são grandes.
    announced_raw = d.get("announced_space")
    announced: dict[str, Any] = cast(dict[str, Any], announced_raw) if isinstance(announced_raw, dict) else {}
    asns_raw = d.get("asns")
    asns = asns_raw if isinstance(asns_raw, list) else []
    countries_raw = d.get("countries")
    countries = countries_raw[:20] if isinstance(countries_raw, list) else []
    out = {
        "asn": int(asn_raw),
        "holder": d.get("holder"),
        "type": d.get("type"),
        "announced_space": {
            "v4": announced.get("v4"),
            "v6": announced.get("v6"),
        },
        "countries": countries,
        "as_set": d.get("as_set"),
        "asns": (asns[:20] if asns else []),
        "source": "stat.ripe.net",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _peeringdb_asn(args: dict[str, Any]) -> ToolResult:
    asn_raw = str(args.get("asn", "") or "").strip().upper().lstrip("AS")
    if not asn_raw or not re.fullmatch(r"\d{1,10}", asn_raw):
        return ToolResult(status="error", error="informe asn (ex: 15169)")

    params = {"asn": int(asn_raw)}
    data, err = _http_json(method="GET", url="https://www.peeringdb.com/api/net", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    items = data.get("data") if isinstance(data.get("data"), list) else []
    item0 = items[0] if items else {}
    if not isinstance(item0, dict):
        item0 = {}
    out = {
        "asn": int(asn_raw),
        "name": item0.get("name"),
        "aka": item0.get("aka"),
        "website": item0.get("website"),
        "irr_as_set": item0.get("irr_as_set"),
        "info_type": item0.get("info_type"),
        "info_scope": item0.get("info_scope"),
        "policy_general": item0.get("policy_general"),
        "policy_locations": item0.get("policy_locations"),
        "policy_ratio": item0.get("policy_ratio"),
        "netixlan_updated": item0.get("netixlan_updated"),
        "source": "www.peeringdb.com",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _urlhaus_url(args: dict[str, Any]) -> ToolResult:
    url_q = str(args.get("url", "") or "").strip().strip('"\'')
    if not url_q:
        return ToolResult(status="error", error="informe url")
    # URLhaus aceita qualquer scheme como string, mas restringimos a URLs comuns.
    if not re.match(r"^https?://", url_q, flags=re.IGNORECASE):
        return ToolResult(status="error", error="url deve começar com http:// ou https://")

    data, err = _http_form(url="https://urlhaus-api.abuse.ch/v1/url/", form_body={"url": url_q}, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    tags_raw = data.get("tags")
    tags = tags_raw[:20] if isinstance(tags_raw, list) else []
    out = {
        "url": url_q,
        "query_status": data.get("query_status"),
        "url_status": data.get("url_status"),
        "host": data.get("host"),
        "firstseen": data.get("firstseen"),
        "lastseen": data.get("lastseen"),
        "threat": data.get("threat"),
        "tags": tags,
        "source": "urlhaus-api.abuse.ch",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _urlhaus_host(args: dict[str, Any]) -> ToolResult:
    host = str(args.get("host", "") or "").strip().lower().strip('"\'').rstrip(".")
    if not host or len(host) > 253 or re.search(r"\s", host):
        return ToolResult(status="error", error="informe host (ex: example.com)")

    data, err = _http_form(url="https://urlhaus-api.abuse.ch/v1/host/", form_body={"host": host}, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    urls_raw = data.get("urls")
    urls = urls_raw if isinstance(urls_raw, list) else []
    slim_urls: list[dict[str, Any]] = []
    for u in urls[:10]:
        if not isinstance(u, dict):
            continue
        slim_urls.append(
            {
                "url": u.get("url"),
                "url_status": u.get("url_status"),
                "firstseen": u.get("firstseen"),
                "lastseen": u.get("lastseen"),
                "threat": u.get("threat"),
            }
        )

    out = {
        "host": host,
        "query_status": data.get("query_status"),
        "host_status": data.get("host_status"),
        "url_count": data.get("url_count"),
        "urls": slim_urls,
        "source": "urlhaus-api.abuse.ch",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _threatfox_ioc_search(args: dict[str, Any]) -> ToolResult:
    ioc = str(args.get("ioc", "") or "").strip().strip('"\'')
    if not ioc:
        return ToolResult(status="error", error="informe ioc")
    try:
        limit = int(args.get("limit", 10) or 10)
    except Exception:
        limit = 10
    if limit < 1:
        limit = 1
    if limit > 25:
        limit = 25

    payload = {"query": "search_ioc", "search_term": ioc}
    data, err = _http_json(method="POST", url="https://threatfox-api.abuse.ch/api/v1/", json_body=payload, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    results_raw = data.get("data")
    results = results_raw if isinstance(results_raw, list) else []
    slim: list[dict[str, Any]] = []
    for r in results[:limit]:
        if not isinstance(r, dict):
            continue
        slim.append(
            {
                "ioc": r.get("ioc"),
                "ioc_type": r.get("ioc_type"),
                "threat_type": r.get("threat_type"),
                "malware": r.get("malware"),
                "confidence_level": r.get("confidence_level"),
                "first_seen": r.get("first_seen"),
                "last_seen": r.get("last_seen"),
            }
        )

    out = {
        "ioc": ioc,
        "query_status": data.get("query_status"),
        "count": len(slim),
        "results": slim,
        "source": "threatfox-api.abuse.ch",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _npm_status(args: dict[str, Any]) -> ToolResult:
    data, err = _http_json(method="GET", url="https://status.npmjs.org/api/v2/status.json", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    page_raw = data.get("page")
    page: dict[str, Any] = cast(dict[str, Any], page_raw) if isinstance(page_raw, dict) else {}
    status_raw = data.get("status")
    status: dict[str, Any] = cast(dict[str, Any], status_raw) if isinstance(status_raw, dict) else {}
    out = {
        "indicator": status.get("indicator"),
        "description": status.get("description"),
        "page": {"name": page.get("name"), "url": page.get("url")},
        "source": "status.npmjs.org",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _openai_status(args: dict[str, Any]) -> ToolResult:
    data, err = _http_json(method="GET", url="https://status.openai.com/api/v2/status.json", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    page_raw = data.get("page")
    page: dict[str, Any] = cast(dict[str, Any], page_raw) if isinstance(page_raw, dict) else {}
    status_raw = data.get("status")
    status: dict[str, Any] = cast(dict[str, Any], status_raw) if isinstance(status_raw, dict) else {}
    out = {
        "indicator": status.get("indicator"),
        "description": status.get("description"),
        "page": {"name": page.get("name"), "url": page.get("url")},
        "source": "status.openai.com",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _docker_status(args: dict[str, Any]) -> ToolResult:
    # Status.io exposes a public JSON endpoint for this page.
    page_id = "533c6539221ae15e3f000031"
    data, err = _http_json(method="GET", url=f"https://www.dockerstatus.com/1.0/status/{page_id}", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    result_raw = data.get("result")
    result: dict[str, Any] = cast(dict[str, Any], result_raw) if isinstance(result_raw, dict) else {}
    overall_raw = result.get("status_overall")
    overall: dict[str, Any] = cast(dict[str, Any], overall_raw) if isinstance(overall_raw, dict) else {}
    out = {
        "status": overall.get("status"),
        "status_code": overall.get("status_code"),
        "updated": overall.get("updated"),
        "source": "www.dockerstatus.com",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _feodotracker_ip_blocklist(args: dict[str, Any]) -> ToolResult:
    try:
        limit = int(args.get("limit", 20) or 20)
    except Exception:
        limit = 20
    if limit < 1:
        limit = 1
    if limit > 50:
        limit = 50

    data, err = _http_json(method="GET", url="https://feodotracker.abuse.ch/downloads/ipblocklist.json", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, list):
        return ToolResult(status="error", error="resposta inesperada")

    slim: list[dict[str, Any]] = []
    for r in data[:limit]:
        if not isinstance(r, dict):
            continue
        slim.append(
            {
                "ip": r.get("ip_address"),
                "port": r.get("port"),
                "status": r.get("status"),
                "hostname": r.get("hostname"),
                "asn": r.get("as_number"),
                "as_name": str(r.get("as_name", "") or "")[:220],
                "country": r.get("country"),
                "first_seen": r.get("first_seen"),
                "last_online": r.get("last_online"),
                "malware": r.get("malware"),
            }
        )

    out = {"count": len(slim), "results": slim, "source": "feodotracker.abuse.ch"}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _hashlookup(args: dict[str, Any]) -> ToolResult:
    algorithm = str(args.get("algorithm", "") or "").strip().lower()
    h = str(args.get("hash", "") or "").strip().lower()
    if algorithm not in {"md5", "sha1", "sha256"}:
        return ToolResult(status="error", error="informe algorithm (md5|sha1|sha256)")
    if not h or not re.fullmatch(r"[0-9a-f]{16,128}", h):
        return ToolResult(status="error", error="informe hash (hex)")

    data, err = _http_json(method="GET", url=f"https://hashlookup.circl.lu/lookup/{quote(algorithm, safe='')}/{quote(h, safe='')}", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    out = {
        "algorithm": algorithm,
        "hash": h,
        "sha1": data.get("SHA-1"),
        "sha256": data.get("SHA-256"),
        "md5": data.get("MD5"),
        "filename": str(data.get("FileName", "") or "")[:240],
        "mimetype": data.get("mimetype"),
        "source": data.get("source"),
        "trust": data.get("hashlookup:trust"),
        "inserted": data.get("insert-timestamp"),
        "source_host": "hashlookup.circl.lu",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _atlassian_status(args: dict[str, Any]) -> ToolResult:
    data, err = _http_json(method="GET", url="https://status.atlassian.com/api/v2/status.json", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    page_raw = data.get("page")
    page: dict[str, Any] = cast(dict[str, Any], page_raw) if isinstance(page_raw, dict) else {}
    status_raw = data.get("status")
    status: dict[str, Any] = cast(dict[str, Any], status_raw) if isinstance(status_raw, dict) else {}
    out = {
        "indicator": status.get("indicator"),
        "description": status.get("description"),
        "page": {"name": page.get("name"), "url": page.get("url")},
        "source": "status.atlassian.com",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _zoom_status(args: dict[str, Any]) -> ToolResult:
    data, err = _http_json(method="GET", url="https://status.zoom.us/api/v2/status.json", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    page_raw = data.get("page")
    page: dict[str, Any] = cast(dict[str, Any], page_raw) if isinstance(page_raw, dict) else {}
    status_raw = data.get("status")
    status: dict[str, Any] = cast(dict[str, Any], status_raw) if isinstance(status_raw, dict) else {}
    out = {
        "indicator": status.get("indicator"),
        "description": status.get("description"),
        "page": {"name": page.get("name"), "url": page.get("url")},
        "source": "status.zoom.us",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _spacex_latest_launch(args: dict[str, Any]) -> ToolResult:
    data, err = _http_json(method="GET", url="https://api.spacexdata.com/v5/launches/latest", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    links_raw = data.get("links")
    links: dict[str, Any] = cast(dict[str, Any], links_raw) if isinstance(links_raw, dict) else {}
    patch_raw = links.get("patch")
    patch: dict[str, Any] = cast(dict[str, Any], patch_raw) if isinstance(patch_raw, dict) else {}
    out = {
        "name": data.get("name"),
        "date_utc": data.get("date_utc"),
        "success": data.get("success"),
        "details": str(data.get("details", "") or "")[:420],
        "webcast": links.get("webcast"),
        "article": links.get("article"),
        "wikipedia": links.get("wikipedia"),
        "patch": {"small": patch.get("small"), "large": patch.get("large")},
        "source": "api.spacexdata.com",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _archiveorg_search(args: dict[str, Any]) -> ToolResult:
    query = str(args.get("query", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe query")

    try:
        limit = int(args.get("limit", 5) or 5)
    except Exception:
        limit = 5
    if limit < 1:
        limit = 1
    if limit > 10:
        limit = 10

    params = {
        "q": query,
        "fl[]": ["identifier", "title", "creator", "date", "mediatype"],
        "rows": limit,
        "page": 1,
        "output": "json",
    }
    data, err = _http_json(method="GET", url="https://archive.org/advancedsearch.php", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    resp_raw = data.get("response")
    resp: dict[str, Any] = cast(dict[str, Any], resp_raw) if isinstance(resp_raw, dict) else {}
    docs_raw = resp.get("docs")
    docs = docs_raw if isinstance(docs_raw, list) else []
    slim: list[dict[str, Any]] = []
    for d in docs[:limit]:
        if not isinstance(d, dict):
            continue
        ident = d.get("identifier")
        url = f"https://archive.org/details/{ident}" if ident else None
        slim.append(
            {
                "identifier": ident,
                "title": d.get("title"),
                "creator": d.get("creator"),
                "date": d.get("date"),
                "mediatype": d.get("mediatype"),
                "url": url,
            }
        )

    out = {"query": query, "count": len(slim), "results": slim, "source": "archive.org"}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _tvmaze_search(args: dict[str, Any]) -> ToolResult:
    query = str(args.get("query", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe query")

    try:
        limit = int(args.get("limit", 5) or 5)
    except Exception:
        limit = 5
    if limit < 1:
        limit = 1
    if limit > 10:
        limit = 10

    data, err = _http_json(method="GET", url="https://api.tvmaze.com/search/shows", params={"q": query}, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, list):
        return ToolResult(status="error", error="resposta inesperada")

    slim: list[dict[str, Any]] = []
    for r in data[:limit]:
        if not isinstance(r, dict):
            continue
        show_raw = r.get("show")
        show: dict[str, Any] = cast(dict[str, Any], show_raw) if isinstance(show_raw, dict) else {}
        rating_raw = show.get("rating")
        rating: dict[str, Any] = cast(dict[str, Any], rating_raw) if isinstance(rating_raw, dict) else {}
        webc_raw = show.get("webChannel")
        webc: dict[str, Any] = cast(dict[str, Any], webc_raw) if isinstance(webc_raw, dict) else {}
        image_raw = show.get("image")
        image: dict[str, Any] = cast(dict[str, Any], image_raw) if isinstance(image_raw, dict) else {}
        genres_raw = show.get("genres")
        genres = genres_raw[:10] if isinstance(genres_raw, list) else []

        network_raw = show.get("network")
        network_name = None
        if isinstance(network_raw, dict):
            network_name = network_raw.get("name")

        slim.append(
            {
                "name": show.get("name"),
                "type": show.get("type"),
                "language": show.get("language"),
                "genres": genres,
                "status": show.get("status"),
                "premiered": show.get("premiered"),
                "officialSite": show.get("officialSite"),
                "url": show.get("url"),
                "rating": rating.get("average"),
                "network": (webc.get("name") or network_name),
                "image": image.get("medium"),
            }
        )

    out = {"query": query, "count": len(slim), "results": slim, "source": "api.tvmaze.com"}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _mealdb_search(args: dict[str, Any]) -> ToolResult:
    query = str(args.get("query", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe query")

    try:
        limit = int(args.get("limit", 5) or 5)
    except Exception:
        limit = 5
    if limit < 1:
        limit = 1
    if limit > 10:
        limit = 10

    data, err = _http_json(method="GET", url="https://www.themealdb.com/api/json/v1/1/search.php", params={"s": query}, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    meals_raw = data.get("meals")
    meals = meals_raw if isinstance(meals_raw, list) else []
    slim: list[dict[str, Any]] = []
    for m in meals[:limit]:
        if not isinstance(m, dict):
            continue
        slim.append(
            {
                "id": m.get("idMeal"),
                "name": m.get("strMeal"),
                "category": m.get("strCategory"),
                "area": m.get("strArea"),
                "tags": m.get("strTags"),
                "instructions": str(m.get("strInstructions", "") or "")[:420],
                "youtube": m.get("strYoutube"),
                "source": m.get("strSource"),
                "thumb": m.get("strMealThumb"),
            }
        )

    out = {"query": query, "count": len(slim), "results": slim, "source": "www.themealdb.com"}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _universities_search(args: dict[str, Any]) -> ToolResult:
    name = str(args.get("name", "") or "").strip()
    if not name:
        return ToolResult(status="error", error="informe name")

    country = str(args.get("country", "") or "").strip()
    try:
        limit = int(args.get("limit", 10) or 10)
    except Exception:
        limit = 10
    if limit < 1:
        limit = 1
    if limit > 25:
        limit = 25

    params: dict[str, Any] = {"name": name}
    if country:
        params["country"] = country

    data, err = _http_json(method="GET", url="https://universities.hipolabs.com/search", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, list):
        return ToolResult(status="error", error="resposta inesperada")

    slim: list[dict[str, Any]] = []
    for u in data[:limit]:
        if not isinstance(u, dict):
            continue
        web_pages_raw = u.get("web_pages")
        web_pages = web_pages_raw if isinstance(web_pages_raw, list) else []
        domains_raw = u.get("domains")
        domains = domains_raw if isinstance(domains_raw, list) else []
        slim.append(
            {
                "name": u.get("name"),
                "country": u.get("country"),
                "alpha_two_code": u.get("alpha_two_code"),
                "state_province": u.get("state-province"),
                "domains": domains[:8],
                "web_pages": web_pages[:4],
            }
        )

    out = {"name": name, "country": country or None, "count": len(slim), "results": slim, "source": "universities.hipolabs.com"}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _agify_name(args: dict[str, Any]) -> ToolResult:
    name = str(args.get("name", "") or "").strip()
    if not name:
        return ToolResult(status="error", error="informe name")
    cc = str(args.get("country_code", "") or "").strip().upper()
    params: dict[str, Any] = {"name": name}
    if cc and re.fullmatch(r"[A-Z]{2}", cc):
        params["country_id"] = cc

    data, err = _http_json(method="GET", url="https://api.agify.io/", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    out = {
        "name": data.get("name") or name,
        "age": data.get("age"),
        "count": data.get("count"),
        "country_id": data.get("country_id") or (cc if cc else None),
        "source": "api.agify.io",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _genderize_name(args: dict[str, Any]) -> ToolResult:
    name = str(args.get("name", "") or "").strip()
    if not name:
        return ToolResult(status="error", error="informe name")
    cc = str(args.get("country_code", "") or "").strip().upper()
    params: dict[str, Any] = {"name": name}
    if cc and re.fullmatch(r"[A-Z]{2}", cc):
        params["country_id"] = cc

    data, err = _http_json(method="GET", url="https://api.genderize.io/", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    out = {
        "name": data.get("name") or name,
        "gender": data.get("gender"),
        "probability": data.get("probability"),
        "count": data.get("count"),
        "country_id": data.get("country_id") or (cc if cc else None),
        "source": "api.genderize.io",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _nationalize_name(args: dict[str, Any]) -> ToolResult:
    name = str(args.get("name", "") or "").strip()
    if not name:
        return ToolResult(status="error", error="informe name")

    try:
        limit = int(args.get("limit", 5) or 5)
    except Exception:
        limit = 5
    if limit < 1:
        limit = 1
    if limit > 10:
        limit = 10

    data, err = _http_json(method="GET", url="https://api.nationalize.io/", params={"name": name}, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    countries_raw = data.get("country")
    countries = countries_raw if isinstance(countries_raw, list) else []
    slim: list[dict[str, Any]] = []
    for c in countries[:limit]:
        if not isinstance(c, dict):
            continue
        slim.append({"country_id": c.get("country_id"), "probability": c.get("probability")})

    out = {
        "name": data.get("name") or name,
        "count": data.get("count"),
        "countries": slim,
        "source": "api.nationalize.io",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _dog_image(args: dict[str, Any]) -> ToolResult:
    data, err = _http_json(method="GET", url="https://dog.ceo/api/breeds/image/random", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    out = {"status": data.get("status"), "image": data.get("message"), "source": "dog.ceo"}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _gitlab_status(args: dict[str, Any]) -> ToolResult:
    data, err = _http_json(method="GET", url="https://status.gitlab.com/api/v2/status.json", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    page_raw = data.get("page")
    page: dict[str, Any] = cast(dict[str, Any], page_raw) if isinstance(page_raw, dict) else {}
    status_raw = data.get("status")
    status: dict[str, Any] = cast(dict[str, Any], status_raw) if isinstance(status_raw, dict) else {}
    out = {
        "indicator": status.get("indicator"),
        "description": status.get("description"),
        "page": {"name": page.get("name"), "url": page.get("url")},
        "source": "status.gitlab.com",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _jikan_anime_search(args: dict[str, Any]) -> ToolResult:
    query = str(args.get("query", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe query")

    try:
        limit = int(args.get("limit", 5) or 5)
    except Exception:
        limit = 5
    if limit < 1:
        limit = 1
    if limit > 10:
        limit = 10

    data, err = _http_json(
        method="GET",
        url="https://api.jikan.moe/v4/anime",
        params={"q": query, "limit": limit},
        timeout_s=12.0,
    )
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    items_raw = data.get("data")
    items = items_raw if isinstance(items_raw, list) else []
    slim: list[dict[str, Any]] = []
    for it in items[:limit]:
        if not isinstance(it, dict):
            continue
        images_raw = it.get("images")
        images: dict[str, Any] = cast(dict[str, Any], images_raw) if isinstance(images_raw, dict) else {}
        jpg_raw = images.get("jpg")
        jpg: dict[str, Any] = cast(dict[str, Any], jpg_raw) if isinstance(jpg_raw, dict) else {}
        slim.append(
            {
                "id": it.get("mal_id"),
                "title": it.get("title"),
                "title_english": it.get("title_english"),
                "year": it.get("year"),
                "episodes": it.get("episodes"),
                "status": it.get("status"),
                "score": it.get("score"),
                "url": it.get("url"),
                "image": jpg.get("image_url"),
                "synopsis": str(it.get("synopsis", "") or "")[:420],
            }
        )

    out = {"query": query, "count": len(slim), "results": slim, "source": "api.jikan.moe"}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _met_search(args: dict[str, Any]) -> ToolResult:
    query = str(args.get("query", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe query")

    try:
        limit = int(args.get("limit", 5) or 5)
    except Exception:
        limit = 5
    if limit < 1:
        limit = 1
    if limit > 10:
        limit = 10

    data, err = _http_json(
        method="GET",
        url="https://collectionapi.metmuseum.org/public/collection/v1/search",
        params={"q": query, "hasImages": "true"},
        timeout_s=12.0,
    )
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    total = data.get("total")
    object_ids_raw = data.get("objectIDs")
    object_ids = object_ids_raw if isinstance(object_ids_raw, list) else []
    top_ids = [oid for oid in object_ids[:limit] if isinstance(oid, int) or (isinstance(oid, str) and str(oid).isdigit())]

    previews: list[dict[str, Any]] = []
    for oid in top_ids[: min(3, len(top_ids))]:
        oid_int = int(oid)
        obj, obj_err = _http_json(
            method="GET",
            url=f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{oid_int}",
            timeout_s=12.0,
        )
        if obj_err or not isinstance(obj, dict):
            continue
        previews.append(
            {
                "object_id": obj.get("objectID") or oid_int,
                "title": obj.get("title"),
                "artist": obj.get("artistDisplayName"),
                "date": obj.get("objectDate"),
                "department": obj.get("department"),
                "image": obj.get("primaryImageSmall"),
                "url": obj.get("objectURL"),
            }
        )

    out = {
        "query": query,
        "total": total,
        "top_object_ids": top_ids,
        "previews": previews,
        "source": "collectionapi.metmuseum.org",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _met_object(args: dict[str, Any]) -> ToolResult:
    oid_raw = args.get("object_id")
    try:
        object_id = int(str(oid_raw or "").strip())
    except Exception:
        object_id = 0
    if object_id <= 0:
        return ToolResult(status="error", error="informe object_id (número)")

    data, err = _http_json(
        method="GET",
        url=f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{object_id}",
        timeout_s=12.0,
    )
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    out = {
        "object_id": data.get("objectID") or object_id,
        "title": data.get("title"),
        "artist": data.get("artistDisplayName"),
        "artist_bio": str(data.get("artistDisplayBio", "") or "")[:220],
        "date": data.get("objectDate"),
        "medium": data.get("medium"),
        "culture": data.get("culture"),
        "department": data.get("department"),
        "dimensions": str(data.get("dimensions", "") or "")[:220],
        "image": data.get("primaryImageSmall") or data.get("primaryImage"),
        "url": data.get("objectURL"),
        "source": "collectionapi.metmuseum.org",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _artic_search(args: dict[str, Any]) -> ToolResult:
    query = str(args.get("query", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe query")

    try:
        limit = int(args.get("limit", 5) or 5)
    except Exception:
        limit = 5
    if limit < 1:
        limit = 1
    if limit > 10:
        limit = 10

    params: dict[str, Any] = {
        "q": query,
        "limit": limit,
        "page": 1,
        "fields": "id,title,artist_title,date_display,image_id,api_link",
    }
    data, err = _http_json(method="GET", url="https://api.artic.edu/api/v1/artworks/search", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    cfg_raw = data.get("config")
    cfg: dict[str, Any] = cast(dict[str, Any], cfg_raw) if isinstance(cfg_raw, dict) else {}
    iiif_url = str(cfg.get("iiif_url") or "").strip()

    items_raw = data.get("data")
    items = items_raw if isinstance(items_raw, list) else []
    slim: list[dict[str, Any]] = []
    for it in items[:limit]:
        if not isinstance(it, dict):
            continue
        image_id = it.get("image_id")
        image_url = None
        if iiif_url and image_id:
            image_url = f"{iiif_url}/{image_id}/full/843,/0/default.jpg"
        slim.append(
            {
                "id": it.get("id"),
                "title": it.get("title"),
                "artist": it.get("artist_title"),
                "date": it.get("date_display"),
                "image": image_url,
                "api_link": it.get("api_link"),
            }
        )

    out = {"query": query, "count": len(slim), "results": slim, "source": "api.artic.edu"}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _chesscom_player(args: dict[str, Any]) -> ToolResult:
    username = str(args.get("username", "") or "").strip().lower()
    if not username or not re.fullmatch(r"[a-z0-9_\-]{2,40}", username):
        return ToolResult(status="error", error="informe username (ex: hikaru)")

    data, err = _http_json(method="GET", url=f"https://api.chess.com/pub/player/{username}", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    out = {
        "username": data.get("username") or username,
        "name": data.get("name"),
        "status": data.get("status"),
        "country": data.get("country"),
        "followers": data.get("followers"),
        "joined": data.get("joined"),
        "last_online": data.get("last_online"),
        "url": data.get("url"),
        "source": "api.chess.com",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _chesscom_stats(args: dict[str, Any]) -> ToolResult:
    username = str(args.get("username", "") or "").strip().lower()
    if not username or not re.fullmatch(r"[a-z0-9_\-]{2,40}", username):
        return ToolResult(status="error", error="informe username (ex: hikaru)")

    data, err = _http_json(method="GET", url=f"https://api.chess.com/pub/player/{username}/stats", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    def _mode_rating(mode_key: str) -> dict[str, Any] | None:
        mode = data.get(mode_key)
        if not isinstance(mode, dict):
            return None
        last_raw = mode.get("last")
        last: dict[str, Any] = cast(dict[str, Any], last_raw) if isinstance(last_raw, dict) else {}
        best_raw = mode.get("best")
        best: dict[str, Any] = cast(dict[str, Any], best_raw) if isinstance(best_raw, dict) else {}
        rec_raw = mode.get("record")
        rec: dict[str, Any] = cast(dict[str, Any], rec_raw) if isinstance(rec_raw, dict) else {}
        return {
            "rating": last.get("rating"),
            "best": best.get("rating"),
            "record": {"win": rec.get("win"), "loss": rec.get("loss"), "draw": rec.get("draw")},
        }

    out = {
        "username": username,
        "blitz": _mode_rating("chess_blitz"),
        "rapid": _mode_rating("chess_rapid"),
        "bullet": _mode_rating("chess_bullet"),
        "tactics": (data.get("tactics") if isinstance(data.get("tactics"), dict) else None),
        "puzzle_rush": (data.get("puzzle_rush") if isinstance(data.get("puzzle_rush"), dict) else None),
        "source": "api.chess.com",
    }
    # Enxuga tactics/puzzle_rush para campos úteis
    if isinstance(out.get("tactics"), dict):
        t = out["tactics"]
        out["tactics"] = {
            "highest": (t.get("highest") if isinstance(t.get("highest"), dict) else {}).get("rating"),
            "lowest": (t.get("lowest") if isinstance(t.get("lowest"), dict) else {}).get("rating"),
        }
    if isinstance(out.get("puzzle_rush"), dict):
        pr = out["puzzle_rush"]
        best = pr.get("best") if isinstance(pr.get("best"), dict) else {}
        out["puzzle_rush"] = {"best": best.get("score")}

    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _chesscom_daily_puzzle(args: dict[str, Any]) -> ToolResult:
    data, err = _http_json(method="GET", url="https://api.chess.com/pub/puzzle", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    out = {
        "title": data.get("title"),
        "url": data.get("url"),
        "publish_time": data.get("publish_time"),
        "image": data.get("image"),
        "pgn": str(data.get("pgn", "") or "")[:1200],
        "source": "api.chess.com",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _openbrewerydb_search(args: dict[str, Any]) -> ToolResult:
    query = str(args.get("query", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe query")

    try:
        limit = int(args.get("limit", 10) or 10)
    except Exception:
        limit = 10
    if limit < 1:
        limit = 1
    if limit > 25:
        limit = 25

    data, err = _http_json(
        method="GET",
        url="https://api.openbrewerydb.org/v1/breweries/search",
        params={"query": query, "per_page": limit},
        timeout_s=12.0,
    )
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, list):
        return ToolResult(status="error", error="resposta inesperada")

    slim: list[dict[str, Any]] = []
    for b in data[:limit]:
        if not isinstance(b, dict):
            continue
        slim.append(
            {
                "id": b.get("id"),
                "name": b.get("name"),
                "type": b.get("brewery_type"),
                "city": b.get("city"),
                "state": b.get("state"),
                "country": b.get("country"),
                "website": b.get("website_url"),
            }
        )

    out = {"query": query, "count": len(slim), "results": slim, "source": "api.openbrewerydb.org"}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _deck_draw(args: dict[str, Any]) -> ToolResult:
    try:
        count = int(args.get("count", 5) or 5)
    except Exception:
        count = 5
    if count < 1:
        count = 1
    if count > 10:
        count = 10

    data, err = _http_json(
        method="GET",
        url="https://deckofcardsapi.com/api/deck/new/draw/",
        params={"count": count},
        timeout_s=12.0,
    )
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    cards_raw = data.get("cards")
    cards = cards_raw if isinstance(cards_raw, list) else []
    slim: list[dict[str, Any]] = []
    for c in cards[:count]:
        if not isinstance(c, dict):
            continue
        slim.append(
            {
                "code": c.get("code"),
                "value": c.get("value"),
                "suit": c.get("suit"),
                "image": c.get("image"),
            }
        )

    out = {
        "deck_id": data.get("deck_id"),
        "remaining": data.get("remaining"),
        "cards": slim,
        "source": "deckofcardsapi.com",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _xkcd_latest(args: dict[str, Any]) -> ToolResult:
    data, err = _http_json(method="GET", url="https://xkcd.com/info.0.json", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    out = {
        "num": data.get("num"),
        "title": data.get("title"),
        "safe_title": data.get("safe_title"),
        "alt": data.get("alt"),
        "img": data.get("img"),
        "day": data.get("day"),
        "month": data.get("month"),
        "year": data.get("year"),
        "link": data.get("link"),
        "source": "xkcd.com",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _xkcd_comic(args: dict[str, Any]) -> ToolResult:
    try:
        num = int(str(args.get("num", "") or "").strip())
    except Exception:
        num = 0
    if num <= 0:
        return ToolResult(status="error", error="informe num (ex: 353)")

    data, err = _http_json(method="GET", url=f"https://xkcd.com/{num}/info.0.json", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    out = {
        "num": data.get("num") or num,
        "title": data.get("title"),
        "safe_title": data.get("safe_title"),
        "alt": data.get("alt"),
        "img": data.get("img"),
        "day": data.get("day"),
        "month": data.get("month"),
        "year": data.get("year"),
        "link": data.get("link"),
        "source": "xkcd.com",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _itunes_search(args: dict[str, Any]) -> ToolResult:
    term = str(args.get("term") or args.get("query") or "").strip()
    if not term:
        return ToolResult(status="error", error="informe term (ou query)")

    media = str(args.get("media", "music") or "music").strip().lower()
    if media not in {"music", "podcast", "movie", "all"}:
        media = "music"

    try:
        limit = int(args.get("limit", 5) or 5)
    except Exception:
        limit = 5
    if limit < 1:
        limit = 1
    if limit > 10:
        limit = 10

    params: dict[str, Any] = {"term": term, "limit": limit}
    if media != "all":
        params["media"] = media

    data, err = _http_json(method="GET", url="https://itunes.apple.com/search", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    results_raw = data.get("results")
    results = results_raw if isinstance(results_raw, list) else []
    slim: list[dict[str, Any]] = []
    for r in results[:limit]:
        if not isinstance(r, dict):
            continue
        slim.append(
            {
                "kind": r.get("kind") or r.get("wrapperType"),
                "trackName": r.get("trackName") or r.get("collectionName"),
                "artistName": r.get("artistName"),
                "collectionName": r.get("collectionName"),
                "releaseDate": r.get("releaseDate"),
                "country": r.get("country"),
                "trackViewUrl": r.get("trackViewUrl") or r.get("collectionViewUrl"),
                "previewUrl": r.get("previewUrl"),
            }
        )

    out = {"term": term, "media": (media if media != "all" else None), "count": len(slim), "results": slim, "source": "itunes.apple.com"}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _gutendex_search(args: dict[str, Any]) -> ToolResult:
    query = str(args.get("query", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe query")

    try:
        limit = int(args.get("limit", 5) or 5)
    except Exception:
        limit = 5
    if limit < 1:
        limit = 1
    if limit > 10:
        limit = 10

    data, err = _http_json(method="GET", url="https://gutendex.com/books", params={"search": query, "page": 1}, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    items_raw = data.get("results")
    items = items_raw if isinstance(items_raw, list) else []
    slim: list[dict[str, Any]] = []
    for b in items[:limit]:
        if not isinstance(b, dict):
            continue
        authors_raw = b.get("authors")
        authors = authors_raw if isinstance(authors_raw, list) else []
        author_names = [a.get("name") for a in authors if isinstance(a, dict) and a.get("name")][:3]
        languages_raw = b.get("languages")
        languages = languages_raw if isinstance(languages_raw, list) else []
        formats_raw = b.get("formats")
        formats: dict[str, Any] = cast(dict[str, Any], formats_raw) if isinstance(formats_raw, dict) else {}
        best = formats.get("text/html") or formats.get("text/html; charset=utf-8") or formats.get("application/epub+zip") or formats.get("application/pdf")
        slim.append(
            {
                "id": b.get("id"),
                "title": b.get("title"),
                "authors": author_names,
                "languages": languages[:5],
                "download_count": b.get("download_count"),
                "link": best,
            }
        )

    out = {"query": query, "count": len(slim), "results": slim, "source": "gutendex.com"}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _openfoodfacts_search(args: dict[str, Any]) -> ToolResult:
    query = str(args.get("query", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe query")

    try:
        limit = int(args.get("limit", 5) or 5)
    except Exception:
        limit = 5
    if limit < 1:
        limit = 1
    if limit > 10:
        limit = 10

    params: dict[str, Any] = {
        "search_terms": query,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": limit,
        "page": 1,
    }
    data, err = _http_json(method="GET", url="https://world.openfoodfacts.org/cgi/search.pl", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    products_raw = data.get("products")
    products = products_raw if isinstance(products_raw, list) else []
    slim: list[dict[str, Any]] = []
    for p in products[:limit]:
        if not isinstance(p, dict):
            continue
        nutr_raw = p.get("nutriments")
        nutr: dict[str, Any] = cast(dict[str, Any], nutr_raw) if isinstance(nutr_raw, dict) else {}
        code = p.get("code")
        url = f"https://world.openfoodfacts.org/product/{code}" if code else p.get("url")
        slim.append(
            {
                "code": code,
                "product_name": p.get("product_name") or p.get("product_name_pt"),
                "brands": p.get("brands"),
                "quantity": p.get("quantity"),
                "nutriscore": p.get("nutriscore_grade"),
                "energy_kcal_100g": nutr.get("energy-kcal_100g"),
                "sugars_100g": nutr.get("sugars_100g"),
                "fat_100g": nutr.get("fat_100g"),
                "salt_100g": nutr.get("salt_100g"),
                "url": url,
            }
        )

    out = {"query": query, "count": len(slim), "results": slim, "source": "world.openfoodfacts.org"}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _npm_downloads_last_week(args: dict[str, Any]) -> ToolResult:
    package = str(args.get("package", "") or "").strip()
    if not package:
        return ToolResult(status="error", error="informe package (ex: express)")

    # npm package names can include scope: @scope/name
    if len(package) > 214:
        return ToolResult(status="error", error="package muito longo")

    safe_pkg = package
    if package.startswith("@") and "/" in package:
        # API expects @scope%2Fname
        safe_pkg = package.replace("/", "%2F")

    data, err = _http_json(method="GET", url=f"https://api.npmjs.org/downloads/point/last-week/{safe_pkg}", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    out = {
        "package": data.get("package") or package,
        "downloads": data.get("downloads"),
        "start": data.get("start"),
        "end": data.get("end"),
        "source": "api.npmjs.org",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _googlebooks_search(args: dict[str, Any]) -> ToolResult:
    query = str(args.get("query", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe query")

    try:
        limit = int(args.get("limit", 5) or 5)
    except Exception:
        limit = 5
    if limit < 1:
        limit = 1
    if limit > 10:
        limit = 10

    params: dict[str, Any] = {
        "q": query,
        "maxResults": limit,
        "printType": "books",
    }
    data, err = _http_json(method="GET", url="https://www.googleapis.com/books/v1/volumes", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    items_raw = data.get("items")
    items = items_raw if isinstance(items_raw, list) else []
    slim: list[dict[str, Any]] = []
    for it in items[:limit]:
        if not isinstance(it, dict):
            continue
        vi_raw = it.get("volumeInfo")
        vi: dict[str, Any] = cast(dict[str, Any], vi_raw) if isinstance(vi_raw, dict) else {}
        links_raw = vi.get("imageLinks")
        links: dict[str, Any] = cast(dict[str, Any], links_raw) if isinstance(links_raw, dict) else {}

        authors_raw = vi.get("authors")
        authors = authors_raw[:5] if isinstance(authors_raw, list) else []
        categories_raw = vi.get("categories")
        categories = categories_raw[:5] if isinstance(categories_raw, list) else []
        slim.append(
            {
                "id": it.get("id"),
                "title": vi.get("title"),
                "authors": authors,
                "publishedDate": vi.get("publishedDate"),
                "categories": categories,
                "pageCount": vi.get("pageCount"),
                "language": vi.get("language"),
                "infoLink": vi.get("infoLink"),
                "previewLink": vi.get("previewLink"),
                "thumbnail": links.get("thumbnail"),
            }
        )

    out = {"query": query, "count": len(slim), "results": slim, "source": "www.googleapis.com"}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _quote_random(args: dict[str, Any]) -> ToolResult:
    data, err = _http_json(method="GET", url="https://api.quotable.io/random", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    tags_raw = data.get("tags")
    tags = tags_raw[:10] if isinstance(tags_raw, list) else []
    out = {
        "content": data.get("content"),
        "author": data.get("author"),
        "tags": tags,
        "source": "api.quotable.io",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _advice_random(args: dict[str, Any]) -> ToolResult:
    data, err = _http_json(method="GET", url="https://api.adviceslip.com/advice", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    slip_raw = data.get("slip")
    slip: dict[str, Any] = cast(dict[str, Any], slip_raw) if isinstance(slip_raw, dict) else {}
    out = {
        "id": slip.get("id"),
        "advice": slip.get("advice"),
        "source": "api.adviceslip.com",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _bored_activity(args: dict[str, Any]) -> ToolResult:
    data, err = _http_json(method="GET", url="https://www.boredapi.com/api/activity", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    out = {
        "activity": data.get("activity"),
        "type": data.get("type"),
        "participants": data.get("participants"),
        "price": data.get("price"),
        "link": data.get("link"),
        "key": data.get("key"),
        "accessibility": data.get("accessibility"),
        "source": "www.boredapi.com",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _fox_image(args: dict[str, Any]) -> ToolResult:
    data, err = _http_json(method="GET", url="https://randomfox.ca/floof/", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    out = {"image": data.get("image"), "link": data.get("link"), "source": "randomfox.ca"}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _duck_image(args: dict[str, Any]) -> ToolResult:
    data, err = _http_json(method="GET", url="https://random-d.uk/api/v2/random", params={"type": "json"}, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    out = {"message": data.get("message"), "image": data.get("url"), "source": "random-d.uk"}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _datamuse_related_words(args: dict[str, Any]) -> ToolResult:
    query = str(args.get("query", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe query")

    relation = str(args.get("relation", "ml") or "ml").strip()
    if relation not in {"ml", "rel_syn", "rel_ant", "rel_rhy"}:
        relation = "ml"

    try:
        max_results = int(args.get("max_results", 10) or 10)
    except Exception:
        max_results = 10
    if max_results < 1:
        max_results = 1
    if max_results > 20:
        max_results = 20

    params: dict[str, Any] = {relation: query, "max": max_results}
    data, err = _http_json(method="GET", url="https://api.datamuse.com/words", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, list):
        return ToolResult(status="error", error="resposta inesperada")

    slim: list[dict[str, Any]] = []
    for it in data[:max_results]:
        if not isinstance(it, dict):
            continue
        slim.append({"word": it.get("word"), "score": it.get("score"), "tags": it.get("tags")})

    out = {
        "query": query,
        "relation": relation,
        "count": len(slim),
        "results": slim,
        "source": "api.datamuse.com",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _scryfall_search(args: dict[str, Any]) -> ToolResult:
    query = str(args.get("query", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe query")

    try:
        limit = int(args.get("limit", 5) or 5)
    except Exception:
        limit = 5
    if limit < 1:
        limit = 1
    if limit > 10:
        limit = 10

    params: dict[str, Any] = {"q": query, "unique": "cards", "order": "released"}
    data, err = _http_json(method="GET", url="https://api.scryfall.com/cards/search", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    cards_raw = data.get("data")
    cards = cards_raw if isinstance(cards_raw, list) else []
    slim: list[dict[str, Any]] = []
    for c in cards[:limit]:
        if not isinstance(c, dict):
            continue
        img_raw = c.get("image_uris")
        img: dict[str, Any] = cast(dict[str, Any], img_raw) if isinstance(img_raw, dict) else {}
        slim.append(
            {
                "name": c.get("name"),
                "mana_cost": c.get("mana_cost"),
                "type_line": c.get("type_line"),
                "oracle_text": c.get("oracle_text"),
                "set": c.get("set"),
                "released_at": c.get("released_at"),
                "scryfall_uri": c.get("scryfall_uri"),
                "image": img.get("normal") or img.get("large") or img.get("small"),
            }
        )

    out = {
        "query": query,
        "count": len(slim),
        "results": slim,
        "source": "api.scryfall.com",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _scryfall_random(args: dict[str, Any]) -> ToolResult:
    data, err = _http_json(method="GET", url="https://api.scryfall.com/cards/random", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    img_raw = data.get("image_uris")
    img: dict[str, Any] = cast(dict[str, Any], img_raw) if isinstance(img_raw, dict) else {}
    out = {
        "name": data.get("name"),
        "mana_cost": data.get("mana_cost"),
        "type_line": data.get("type_line"),
        "oracle_text": data.get("oracle_text"),
        "set": data.get("set"),
        "released_at": data.get("released_at"),
        "scryfall_uri": data.get("scryfall_uri"),
        "image": img.get("normal") or img.get("large") or img.get("small"),
        "source": "api.scryfall.com",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _rickmorty_character_search(args: dict[str, Any]) -> ToolResult:
    query = str(args.get("query", "") or "").strip()
    if not query:
        return ToolResult(status="error", error="informe query")

    try:
        limit = int(args.get("limit", 5) or 5)
    except Exception:
        limit = 5
    if limit < 1:
        limit = 1
    if limit > 10:
        limit = 10

    data, err = _http_json(
        method="GET",
        url="https://rickandmortyapi.com/api/character/",
        params={"name": query},
        timeout_s=12.0,
    )
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    results_raw = data.get("results")
    results = results_raw if isinstance(results_raw, list) else []
    slim: list[dict[str, Any]] = []
    for c in results[:limit]:
        if not isinstance(c, dict):
            continue
        origin_raw = c.get("origin")
        origin: dict[str, Any] = cast(dict[str, Any], origin_raw) if isinstance(origin_raw, dict) else {}
        location_raw = c.get("location")
        location: dict[str, Any] = cast(dict[str, Any], location_raw) if isinstance(location_raw, dict) else {}
        slim.append(
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "status": c.get("status"),
                "species": c.get("species"),
                "type": c.get("type"),
                "gender": c.get("gender"),
                "origin": origin.get("name"),
                "location": location.get("name"),
                "image": c.get("image"),
                "url": c.get("url"),
            }
        )

    info_raw = data.get("info")
    info: dict[str, Any] = cast(dict[str, Any], info_raw) if isinstance(info_raw, dict) else {}
    out = {
        "query": query,
        "count": len(slim),
        "total": info.get("count"),
        "results": slim,
        "source": "rickandmortyapi.com",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _sunrise_sunset(args: dict[str, Any]) -> ToolResult:
    try:
        lat = float(str(args.get("lat")).replace(",", "."))
        lon = float(str(args.get("lon")).replace(",", "."))
    except Exception:
        return ToolResult(status="error", error="informe lat e lon (números)")

    date = str(args.get("date", "") or "").strip()
    if date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        return ToolResult(status="error", error="date deve ser YYYY-MM-DD")
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    params: dict[str, Any] = {"lat": lat, "lng": lon, "date": date, "formatted": 0}
    data, err = _http_json(method="GET", url="https://api.sunrise-sunset.org/json", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    results_raw = data.get("results")
    results: dict[str, Any] = cast(dict[str, Any], results_raw) if isinstance(results_raw, dict) else {}
    out = {
        "lat": lat,
        "lon": lon,
        "date": date,
        "timezone": "UTC",
        "sunrise": results.get("sunrise"),
        "sunset": results.get("sunset"),
        "solar_noon": results.get("solar_noon"),
        "day_length": results.get("day_length"),
        "civil_twilight_begin": results.get("civil_twilight_begin"),
        "civil_twilight_end": results.get("civil_twilight_end"),
        "status": data.get("status"),
        "source": "api.sunrise-sunset.org",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _dadjoke(args: dict[str, Any]) -> ToolResult:
    data, err = _http_json(
        method="GET",
        url="https://icanhazdadjoke.com/",
        headers={"Accept": "application/json"},
        timeout_s=12.0,
    )
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")

    out = {"id": data.get("id"), "joke": data.get("joke"), "source": "icanhazdadjoke.com"}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _jokeapi(args: dict[str, Any]) -> ToolResult:
    category = str(args.get("category", "Any") or "Any").strip()
    if not re.fullmatch(r"[A-Za-z,]{2,60}", category):
        category = "Any"

    params: dict[str, Any] = {
        "type": "single",
        "safe-mode": "",
        "blacklistFlags": "nsfw,religious,political,racist,sexist,explicit",
    }
    data, err = _http_json(method="GET", url=f"https://v2.jokeapi.dev/joke/{category}", params=params, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")
    if data.get("error") is True:
        return ToolResult(status="error", error=str(data.get("message") or "erro")[:200])

    out = {
        "category": data.get("category"),
        "joke": data.get("joke"),
        "lang": data.get("lang"),
        "safe": data.get("safe"),
        "source": "v2.jokeapi.dev",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _ibge_states(args: dict[str, Any]) -> ToolResult:
    data, err = _http_json(method="GET", url="https://servicodados.ibge.gov.br/api/v1/localidades/estados", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, list):
        return ToolResult(status="error", error="resposta inesperada")

    slim: list[dict[str, Any]] = []
    for s in data:
        if not isinstance(s, dict):
            continue
        reg_raw = s.get("regiao")
        reg: dict[str, Any] = cast(dict[str, Any], reg_raw) if isinstance(reg_raw, dict) else {}
        slim.append({"id": s.get("id"), "sigla": s.get("sigla"), "nome": s.get("nome"), "regiao": reg.get("nome")})

    slim.sort(key=lambda x: (str(x.get("sigla") or "")))
    out = {"count": len(slim), "states": slim, "source": "servicodados.ibge.gov.br"}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _ibge_municipalities_by_uf(args: dict[str, Any]) -> ToolResult:
    uf = str(args.get("uf", "") or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", uf):
        return ToolResult(status="error", error="informe uf (ex: SP)")

    try:
        limit = int(args.get("limit", 20) or 20)
    except Exception:
        limit = 20
    if limit < 1:
        limit = 1
    if limit > 50:
        limit = 50

    url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"
    data, err = _http_json(method="GET", url=url, timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, list):
        return ToolResult(status="error", error="resposta inesperada")

    slim: list[dict[str, Any]] = []
    for m in data[:limit]:
        if not isinstance(m, dict):
            continue
        slim.append({"id": m.get("id"), "nome": m.get("nome")})

    out = {"uf": uf, "count": len(slim), "municipalities": slim, "source": "servicodados.ibge.gov.br"}
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))


def _viacep_lookup(args: dict[str, Any]) -> ToolResult:
    cep = str(args.get("cep", "") or "").strip()
    cep_digits = re.sub(r"\D+", "", cep)
    if not re.fullmatch(r"\d{8}", cep_digits):
        return ToolResult(status="error", error="informe cep com 8 dígitos (ex: 01001000)")

    data, err = _http_json(method="GET", url=f"https://viacep.com.br/ws/{cep_digits}/json/", timeout_s=12.0)
    if err:
        return ToolResult(status="error", error=err)
    if not isinstance(data, dict):
        return ToolResult(status="error", error="resposta inesperada")
    if data.get("erro") is True:
        return ToolResult(status="error", error="CEP não encontrado")

    out = {
        "cep": data.get("cep") or cep_digits,
        "logradouro": data.get("logradouro"),
        "complemento": data.get("complemento"),
        "bairro": data.get("bairro"),
        "localidade": data.get("localidade"),
        "uf": data.get("uf"),
        "ibge": data.get("ibge"),
        "gia": data.get("gia"),
        "ddd": data.get("ddd"),
        "siafi": data.get("siafi"),
        "source": "viacep.com.br",
    }
    return ToolResult(status="ok", output=json.dumps(out, ensure_ascii=False))
