import asyncio
import sys
import io

# Fix Windows console encoding for emoji
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from app.db.mongo import connect_db, close_db
from app.backend.ingestion.tmdb_client import close_client
from app.services.tmdb_sync_service import (
    sync_trending_movies,
    sync_trending_tv,
    add_movie_by_title,
    add_tv_series_by_title,
)


async def main():
    print("Connecting to MongoDB...")
    await connect_db()
    print("Connected. Starting TMDB sync...\n")

    # --- Trending (2 pages = ~40 movies + ~40 TV series) ---
    print("=== Fetching Trending Movies (2 pages) ===")
    movies_result = await sync_trending_movies(pages=2)
    print(f"Movies result: saved={movies_result['saved']}, failed={movies_result['failed']}\n")

    print("=== Fetching Trending TV Series (2 pages) ===")
    tv_result = await sync_trending_tv(pages=2)
    print(f"TV Series result: saved={tv_result['saved']}, failed={tv_result['failed']}\n")

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

    await close_client()
    await close_db()
    print("Done.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        import traceback
        traceback.print_exc()