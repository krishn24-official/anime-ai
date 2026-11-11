"""Find and remove adult (18+) titles: movies/TV by TMDb adult keywords, anime/manga by
AniList's adult flag. Rules: app/domain/media/adult.py.

    python -m app.scripts.remove_adult_content            # DRY RUN: list what would be removed
    python -m app.scripts.remove_adult_content --apply    # back up to backups/, then remove

Titles are soft-deleted and marked is_adult (so importers never bring them back);
trending, ratings, watchlists, comments, relationships, events, episodes/chapters and
characters that only belonged to removed titles are cleaned up.
"""

import argparse
import asyncio

from pymongo import AsyncMongoClient

import app.db.mongo as mongo
from app.config import MONGO_URI
from app.services.adult_content_service import find_all, remove


async def main(apply: bool) -> None:
    mongo.client = AsyncMongoClient(MONGO_URI)  # no startup index work
    try:
        found = await find_all()
        for collection, items in found.items():
            print(f"{collection:10} {len(items):4} adult titles")
            for item in items[:15]:
                print(f"     {str(item['title'])[:50]:50} {item['reason']}")
            if len(items) > 15:
                print(f"     ... and {len(items) - 15} more")
        if not apply:
            print("\nDRY RUN: nothing changed. Run with --apply to remove (a backup is written first).")
            return
        print(await remove(found))
    finally:
        await mongo.client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="remove (default is a dry run)")
    asyncio.run(main(parser.parse_args().apply))
