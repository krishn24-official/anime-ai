import asyncio

from app.db.mongo import connect_db, close_db
from app.services.tmdb_sync_service import (
    sync_trending_movies,
    sync_trending_tv,
    add_movie_by_title,
    add_tv_series_by_title,
)


async def main():
    print("Connecting to MongoDB...")
    await connect_db()
    print("Connected. Starting TMDB sync...")

    # --- Trending (default) ---
    movies_result = await sync_trending_movies(pages=2)
    print("🎬 Trending movies:", movies_result)

    tv_result = await sync_trending_tv(pages=2)
    print("📺 Trending TV series:", tv_result)

    # --- Specific titles (optional) ---
    # Uncomment and edit to add specific titles:
    #
    # for title in ["Mission Impossible", "Inception"]:
    #     doc = await add_movie_by_title(title)
    #     print("Added movie:", doc["_id"] if doc else f"NOT FOUND: {title}")
    #
    # for title in ["Loki", "Breaking Bad"]:
    #     doc = await add_tv_series_by_title(title)
    #     print("Added TV series:", doc["_id"] if doc else f"NOT FOUND: {title}")

    await close_db()
    print("Done.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        import traceback
        traceback.print_exc()