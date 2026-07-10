"""
fetch_all.py  -  One-command TMDb bulk ingestion
=====================================================
Fetches movies and TV series from TMDb using paginated
discovery queries (sorted by popularity).

Usage:
    python -m app.backend.ingestion.tmdb.fetch_all
    python -m app.backend.ingestion.tmdb.fetch_all --movie-pages 5 --tv-pages 5
    python -m app.backend.ingestion.tmdb.fetch_all --only movies
    python -m app.backend.ingestion.tmdb.fetch_all --only tv
"""

import argparse
import asyncio
import sys
import io

# Fix Windows console encoding for emoji / CJK
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from app.db.mongo import connect_db, close_db
from app.backend.ingestion.tmdb_client import close_client
from app.services.tmdb_sync_service import (
    sync_discover_movies,
    sync_discover_tv,
)

async def main():
    parser = argparse.ArgumentParser(description="TMDb bulk ingestion")
    parser.add_argument("--movie-pages", type=int, default=5, help="Pages of movies to fetch (20 per page)")
    parser.add_argument("--tv-pages", type=int, default=5, help="Pages of TV series to fetch (20 per page)")
    parser.add_argument(
        "--only",
        choices=["movies", "tv", "all"],
        default="all",
        help="Fetch only a specific type",
    )
    args = parser.parse_args()

    print("Connecting to MongoDB...")
    await connect_db()
    print("Connected. Starting TMDb bulk sync...\n")

    results = {}

    try:
        if args.only in ("all", "movies"):
            print(f"=== Discovering Popular Movies ({args.movie_pages} pages) ===")
            results["movies"] = await sync_discover_movies(pages=args.movie_pages, sort_by="popularity.desc")
            print(f"Movies result: saved={results['movies']['saved']}, failed={results['movies']['failed']}\n")

        if args.only in ("all", "tv"):
            print(f"=== Discovering Popular TV Series ({args.tv_pages} pages) ===")
            results["tv"] = await sync_discover_tv(pages=args.tv_pages, sort_by="popularity.desc")
            print(f"TV Series result: saved={results['tv']['saved']}, failed={results['tv']['failed']}\n")
            
    finally:
        await close_client()
        await close_db()
        
    # --- Summary ---
    print(f"\n{'='*60}")
    print("  TMDb INGESTION COMPLETE")
    print(f"{'='*60}")
    for category, stats in results.items():
        print(f"  {category.upper():>12}: saved={stats['saved']}, failed={stats['failed']}")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    except Exception:
        import traceback
        traceback.print_exc()
