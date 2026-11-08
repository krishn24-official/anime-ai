"""Rebuild one series' RAG lore from its episode wiki pages (no PDF step).

    python -m app.scripts.rebuild_lore --series anime_bleach              # dry run: fetch + parse, report
    python -m app.scripts.rebuild_lore --series anime_bleach --apply      # replace the series' passages
    python -m app.scripts.rebuild_lore --series anime_one_piece --limit 20

--apply also fills in episode titles/summaries in the `episodes` collection, and
writes a JSON backup of the old passages to backups/ before deleting them
(restore by re-inserting that file). One series at a time, by design.
"""

import argparse
import asyncio

from pymongo import AsyncMongoClient

import app.db.mongo as mongo
from app import container
from app.config import MONGO_DB_NAME, MONGO_URI
from app.infrastructure.wiki.fandom_episode_source import WIKIS


async def storage_mb() -> float:
    stats = await mongo.client[MONGO_DB_NAME].command("dbstats")
    return round((stats["dataSize"] + stats["indexSize"]) / 1e6, 1)


async def main(series: str, apply: bool, limit: int | None) -> None:
    mongo.client = AsyncMongoClient(MONGO_URI)  # no startup index work
    try:
        before = await storage_mb()
        report = await container.lore_rebuild_service().rebuild(series, apply=apply, limit=limit)
        print(f"series            {report.series_id}")
        print(f"episodes stored   {report.episodes}")
        print(f"wiki pages found  {report.pages_found}")
        print(f"with a story      {report.with_story}")
        print(f"passages built    {report.passages}")
        for p in report.sample:
            print(f"\n--- sample: {p.section_title}\n{p.text[:400]}")
        if report.applied:
            print(f"\napplied: {report.store_stats}")
            print(f"database size     {before} MB -> {await storage_mb()} MB (Atlas free tier: 512 MB)")
        else:
            print("\nDRY RUN: nothing was written. Re-run with --apply.")
    finally:
        await mongo.client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--series", required=True, choices=sorted(WIKIS))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, help="only the first N episodes (for trying it out)")
    args = parser.parse_args()
    asyncio.run(main(args.series, args.apply, args.limit))
