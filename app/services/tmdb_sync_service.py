from app.backend.ingestion.tmdb_client import (
    get_trending_movies,
    get_trending_tv,
    search_movie,
    search_tv,
    get_movie_details,
    get_tv_details,
)
from app.backend.ingestion.tmdb_mapper import map_movie, map_tv_series
from app.repositories.movie_repository import upsert_movie
from app.repositories.tv_series_repository import upsert_tv_series


async def sync_trending_movies(pages: int = 1) -> dict:
    saved = 0
    failed = 0

    for page in range(1, pages + 1):
        results = await get_trending_movies(page=page)

        for item in results:
            details = await get_movie_details(item["id"])

            if not details:
                failed += 1
                continue

            await upsert_movie(map_movie(details))
            saved += 1

    return {"saved": saved, "failed": failed}


async def sync_trending_tv(pages: int = 1) -> dict:
    saved = 0
    failed = 0

    for page in range(1, pages + 1):
        results = await get_trending_tv(page=page)

        for item in results:
            details = await get_tv_details(item["id"])

            if not details:
                failed += 1
                continue

            await upsert_tv_series(map_tv_series(details))
            saved += 1

    return {"saved": saved, "failed": failed}


async def add_movie_by_title(title: str) -> dict | None:
    """Search TMDB for a movie title and ingest the top match."""
    results = await search_movie(title)

    if not results:
        return None

    details = await get_movie_details(results[0]["id"])

    if not details:
        return None

    doc = map_movie(details)
    await upsert_movie(doc)

    return doc


async def add_tv_series_by_title(title: str) -> dict | None:
    """Search TMDB for a TV series title and ingest the top match."""
    results = await search_tv(title)

    if not results:
        return None

    details = await get_tv_details(results[0]["id"])

    if not details:
        return None

    doc = map_tv_series(details)
    await upsert_tv_series(doc)

    return doc


async def run_tmdb_sync(pages: int = 1) -> dict:
    """Sync trending movies and TV series. Used by both the scheduler and
    the manual /movies/sync-like trigger."""

    movies_result = await sync_trending_movies(pages=pages)
    tv_result = await sync_trending_tv(pages=pages)

    return {
        "movies": movies_result,
        "tv_series": tv_result,
    }