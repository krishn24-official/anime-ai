"""Link already-stored copies of the same story (from different sources) to the first one.

    python -m app.scripts.merge_duplicate_news              # dry run: list the groups
    python -m app.scripts.merge_duplicate_news --apply      # mark duplicates
    python -m app.scripts.merge_duplicate_news --days 30 --apply

New articles are merged as they arrive (news_pipeline_service); this catches up
on what was stored before. A duplicate keeps its document (so its URL is never
fetched again) but gets `duplicate_of` and disappears from listings; the original
lists it under `also_reported_by`. Undo: unset `duplicate_of` on the duplicates.
"""

import argparse
import asyncio
from datetime import datetime, timedelta

from pymongo import AsyncMongoClient, UpdateOne

import app.db.mongo as mongo
from app.config import MONGO_URI, MONGO_DB_NAME
from app.domain.news.duplicates import find_original
from app.services.news_dedup import headlines


async def main(days: int, apply: bool) -> None:
    mongo.client = AsyncMongoClient(MONGO_URI)
    news = mongo.client[MONGO_DB_NAME]["news"]
    try:
        docs = await news.find(
            {"duplicate_of": {"$exists": False}, "published_at": {"$gte": datetime.utcnow() - timedelta(days=days)}},
            {"title": 1, "source": 1, "url": 1, "published_at": 1},
        ).sort("published_at", 1).to_list(None)

        parsed = await headlines(docs)
        recent, ops, groups = [], [], {}
        for d, headline in zip(docs, parsed):
            original = find_original(headline, d.get("source"), recent)
            if original is None:
                recent.append((d["_id"], d.get("source"), headline))
                continue
            groups.setdefault(original, []).append(d)
            ops.append(UpdateOne({"_id": d["_id"]}, {"$set": {"duplicate_of": original}}))
            ops.append(UpdateOne(
                {"_id": original},
                {"$addToSet": {"also_reported_by": {"source": d.get("source"), "url": d.get("url")}}},
            ))

        titles = {d["_id"]: f"{d.get('source')}: {d.get('title')}" for d in docs}
        for original, dups in groups.items():
            print(f"KEEP  {titles[original]}")
            for d in dups:
                print(f"  dup {titles[d['_id']]}")
        print(f"\n{len(docs)} articles checked, {sum(map(len, groups.values()))} duplicates in {len(groups)} stories")

        if apply and ops:
            await news.bulk_write(ops, ordered=True)
            print("Applied.")
        elif not apply:
            print("DRY RUN: nothing was written. Re-run with --apply.")
    finally:
        await mongo.client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=14, help="how far back to look")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.days, args.apply))
