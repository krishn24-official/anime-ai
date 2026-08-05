from app.backend.ingestion.tmdb_client import (
    get_trending_movies,
    get_trending_tv,
    search_movie,
    search_tv,
    get_movie_details,
    get_tv_details,
    discover_movies,
    discover_tv,
)
from app.backend.ingestion.tmdb_mapper import map_movie, map_tv_series
from app.repositories.movie_repository import upsert_movie
from app.repositories.tv_series_repository import upsert_tv_series
from app.services.cast_reconciliation_service import reconcile_cast, reconcile_directors, reconcile_creators, reconcile_writers


async def sync_discover_movies(pages: int = 5, max_cast: int = 10, sort_by: str = "popularity.desc", **filters) -> dict:
    saved = 0
    failed = 0

    for page in range(1, pages + 1):
        response = await discover_movies(page=page, sort_by=sort_by, **filters)
        results = response.get("results", [])
        print(f"  Page {page}: found {len(results)} movies")

        for item in results:
            details = await get_movie_details(item["id"])

            if not details:
                failed += 1
                print(f"    [FAIL] Could not fetch details for tmdb_id={item['id']}")
                continue

            doc = map_movie(details, max_cast=max_cast)
            doc["director"] = await reconcile_directors(doc.get("director", []))
            doc["writer"] = await reconcile_writers(doc.get("writers", []))
            doc["cast"] = await reconcile_cast(doc.get("cast", []))
            await upsert_movie(doc)
            saved += 1
            print(f"    [OK] {doc['_id']} - {doc['title']} ({doc.get('year', '?')})")

    return {"saved": saved, "failed": failed}


async def sync_discover_tv(pages: int = 5, max_cast: int = 10, sort_by: str = "popularity.desc", **filters) -> dict:
    saved = 0
    failed = 0

    for page in range(1, pages + 1):
        response = await discover_tv(page=page, sort_by=sort_by, **filters)
        results = response.get("results", [])
        print(f"  Page {page}: found {len(results)} TV series")

        for item in results:
            details = await get_tv_details(item["id"])

            if not details:
                failed += 1
                print(f"    [FAIL] Could not fetch details for tmdb_id={item['id']}")
                continue

            doc = map_tv_series(details, max_cast=max_cast)
            doc["creators"] = await reconcile_creators(doc.get("creators", []))
            doc["cast"] = await reconcile_cast(doc.get("cast", []))
            await upsert_tv_series(doc)
            saved += 1
            print(f"    [OK] {doc['_id']} - {doc['title']} ({doc.get('year', '?')})")

    return {"saved": saved, "failed": failed}


async def sync_trending_movies(pages: int = 1) -> dict:
    saved = 0
    failed = 0

    for page in range(1, pages + 1):
        results = await get_trending_movies(page=page)
        print(f"  Page {page}: found {len(results)} trending movies")

        for item in results:
            details = await get_movie_details(item["id"])

            if not details:
                failed += 1
                print(f"    [FAIL] Could not fetch details for tmdb_id={item['id']}")
                continue

            doc = map_movie(details)
            doc["director"] = await reconcile_directors(doc.get("director", []))
            doc["writer"] = await reconcile_writers(doc.get("writers", []))
            doc["cast"] = await reconcile_cast(doc.get("cast", []))
            await upsert_movie(doc)
            saved += 1
            print(f"    [OK] {doc['_id']} - {doc['title']} ({doc.get('year', '?')})")

    return {"saved": saved, "failed": failed}


async def sync_trending_tv(pages: int = 1) -> dict:
    saved = 0
    failed = 0

    for page in range(1, pages + 1):
        results = await get_trending_tv(page=page)
        print(f"  Page {page}: found {len(results)} trending TV series")

        for item in results:
            details = await get_tv_details(item["id"])

            if not details:
                failed += 1
                print(f"    [FAIL] Could not fetch details for tmdb_id={item['id']}")
                continue

            doc = map_tv_series(details)
            doc["creators"] = await reconcile_creators(doc.get("creators", []))
            doc["cast"] = await reconcile_cast(doc.get("cast", []))
            await upsert_tv_series(doc)
            saved += 1
            print(f"    [OK] {doc['_id']} - {doc['title']} ({doc.get('year', '?')})")

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
    doc["director"] = await reconcile_directors(doc.get("director", []))
    doc["writer"] = await reconcile_writers(doc.get("writers", []))
    doc["cast"] = await reconcile_cast(doc.get("cast", []))
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
    doc["creators"] = await reconcile_creators(doc.get("creators", []))
    doc["cast"] = await reconcile_cast(doc.get("cast", []))
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