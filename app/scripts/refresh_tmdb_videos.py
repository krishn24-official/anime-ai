"""Refresh trailers, posters and upcoming release dates from TMDb.

    python -m app.scripts.refresh_tmdb_videos --dry-run              # report only
    python -m app.scripts.refresh_tmdb_videos --kind movie --limit 2000
    python -m app.scripts.refresh_tmdb_videos --kind all --limit 500
    python -m app.scripts.refresh_tmdb_videos --active-only --limit 20000   # upcoming/recent only

The scheduler runs the same refresh daily with smaller limits; use this to catch up
faster (e.g. right after deploying the fix). Upcoming/recent titles go first.
"""

import argparse
import asyncio

from pymongo import AsyncMongoClient

import app.db.mongo as mongo
from app.config import MONGO_URI
from app.services.tmdb_video_refresh_service import refresh


async def main(kind: str, limit: int, dry_run: bool, active_only: bool) -> None:
    mongo.client = AsyncMongoClient(MONGO_URI)  # no startup index work
    try:
        for k in (["movie", "tv"] if kind == "all" else [kind]):
            print(k, await refresh(k, limit, dry_run=dry_run, active_only=active_only), flush=True)
        if dry_run:
            print("DRY RUN: nothing was written.")
    finally:
        await mongo.client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--kind", choices=["movie", "tv", "all"], default="all")
    parser.add_argument("--limit", type=int, default=200, help="titles per kind")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--active-only", action="store_true", help="only upcoming/recent titles")
    args = parser.parse_args()
    asyncio.run(main(args.kind, args.limit, args.dry_run, args.active_only))
