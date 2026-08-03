from app.repositories.search_repository import (
    search_characters,
    search_anime,
    search_manga,
    search_movies,
    search_tv_series,
    search_organizations,
)
from app.repositories.actors_repository import search_actors


async def global_search(
    query: str
):

    characters = await search_characters(query)
    anime = await search_anime(query)
    manga = await search_manga(query)
    movies = await search_movies(query)
    tv_series = await search_tv_series(query)
    organizations = await search_organizations(query)
    actors = await search_actors(query, limit=5)

    return {
        "characters": characters,
        "anime": anime,
        "manga": manga,
        "movies": movies,
        "tv_series": tv_series,
        "organizations": organizations,
        "actors": actors,
    }