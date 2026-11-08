"""Free Atlas space: old news and low-relevance actors (see app/services/data_retention_service.py).

    python -m app.scripts.prune_data news            # dry run: how many would go
    python -m app.scripts.prune_data news --apply    # delete news older than 15 days
    python -m app.scripts.prune_data actors --apply  # delete low-relevance actors (and their cast entries)
    python -m app.scripts.prune_data cast --apply    # drop cast/crew entries whose actor no longer exists

Everything deleted is first written to backups/*.json.gz.
"""

import argparse
import asyncio

from pymongo import AsyncMongoClient

import app.db.mongo as mongo
from app.config import MONGO_DB_NAME, MONGO_URI
from app.services.data_retention_service import prune_actors, prune_news, remove_orphan_people


async def storage_mb() -> float:
    stats = await mongo.client[MONGO_DB_NAME].command("dbstats")
    return round((stats["dataSize"] + stats["indexSize"]) / 1e6, 1)


async def main(what: str, apply: bool) -> None:
    mongo.client = AsyncMongoClient(MONGO_URI)
    try:
        before = await storage_mb()
        jobs = {"news": prune_news, "actors": prune_actors, "cast": remove_orphan_people}
        stats = await jobs[what](apply=apply)
        for k, v in stats.items():
            print(f"{k:28} {v}")
        if apply:
            print(f"{'database size':28} {before} MB -> {await storage_mb()} MB")
        else:
            print("DRY RUN: nothing was deleted. Re-run with --apply.")
    finally:
        await mongo.client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("what", choices=["news", "actors", "cast"])
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.what, args.apply))
