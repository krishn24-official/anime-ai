"""Keeping the database inside the Atlas free tier (512 MB).

- News: articles older than NEWS_RETENTION_DAYS are deleted (admin-written ones are kept).
  Runs daily from the scheduler.
- Actors: people who are neither popular themselves (TMDb person popularity, from
  TMDb's free daily export) nor in a big or currently popular title are deleted,
  and removed from the titles' cast/crew lists too (re-add an actor to bring them back).
"""

import asyncio
import gzip
import io
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import httpx
from bson import json_util
from pymongo import UpdateOne
from pymongo.errors import PyMongoError

from app.db.mongo import get_db

NEWS_RETENTION_DAYS = 15
BIG_TITLE_VOTES = 1000  # an actor in any title with this many TMDb votes is kept
POPULAR_TITLE = 20.0  # ...or in a title this popular right now (big upcoming films have 0 votes)
# ...or popular themselves: 0.75 is about the world's top 40k people on TMDb, and keeps
# stars whose own titles here are small or upcoming (Nayanthara 2.8, Kartik Aaryan 0.82).
POPULAR_PERSON = 0.75
TMDB_EXPORT_URL = "https://files.tmdb.org/p/exports/person_ids_{date}.json.gz"
NAME_COPY_BATCH = 500  # titles per bulk write
DELETE_BATCH = 1000  # small enough for the free tier not to cancel it
PEOPLE_FIELDS = ("cast", "director", "writer", "creators", "producers")
TITLE_COLLECTIONS = ("movies", "tv_series")


def _backup(name: str, docs: list) -> str | None:
    if not docs:
        return None
    os.makedirs("backups", exist_ok=True)
    path = os.path.join("backups", f"{name}_{datetime.now():%Y%m%d_%H%M%S}.json.gz")
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write(json_util.dumps(docs))
    return path


async def prune_news(days: int = NEWS_RETENTION_DAYS, apply: bool = False, backup: bool = True) -> dict:
    db = get_db()
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)  # stored as naive UTC
    old = {"published_at": {"$lt": cutoff}, "source": {"$ne": "manual"}}
    stats = {
        "news_to_delete": await db.news.count_documents(old),
        "news_kept": await db.news.count_documents({"$nor": [old]}),
    }
    if not apply or not stats["news_to_delete"]:
        return stats
    docs = await db.news.find(old).to_list(None)
    if backup:  # manual runs keep a copy; the daily scheduler run does not pile files up
        stats["backup"] = _backup("news", docs)
    ids = [d["_id"] for d in docs]
    stats["news_deleted"] = (await db.news.delete_many({"_id": {"$in": ids}})).deleted_count
    # Trending mentions point at articles; old ones are outside every trending window anyway.
    stats["mentions_deleted"] = (await db.trending_mentions.delete_many(
        {"$or": [{"news_id": {"$in": [str(i) for i in ids]}}, {"news_id": {"$in": ids}}]}
    )).deleted_count
    return stats


async def _actor_relevance() -> tuple[dict, dict]:
    """actor id -> (biggest linked title's votes, its popularity) and actor id -> titles."""
    votes, popularity, linked = defaultdict(int), defaultdict(float), defaultdict(list)
    for col in TITLE_COLLECTIONS:
        cursor = get_db()[col].find(
            {"is_deleted": {"$ne": True}}, {**{f: 1 for f in PEOPLE_FIELDS}, "rating": 1, "popularity": 1}
        )
        async for d in cursor:
            v = int((d.get("rating") or {}).get("tmdb_vote_count") or 0)
            p = float(d.get("popularity") or 0)
            for f in PEOPLE_FIELDS:
                for entry in d.get(f) or []:
                    if isinstance(entry, dict) and entry.get("actor_id"):
                        a = entry["actor_id"]
                        votes[a], popularity[a] = max(votes[a], v), max(popularity[a], p)
                        linked[a].append((col, d["_id"]))
    return {a: (votes[a], popularity[a]) for a in votes}, linked


async def _person_popularity() -> dict[int, float]:
    """TMDb id -> popularity for every person, from TMDb's daily export (one ~75 MB
    download, read in memory: nothing is written to disk)."""
    async with httpx.AsyncClient(timeout=300, follow_redirects=True) as http:
        for days_back in range(3):  # today's file may not be published yet
            date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%m_%d_%Y")
            r = await http.get(TMDB_EXPORT_URL.format(date=date))
            if r.status_code == 200:
                break
        else:
            raise RuntimeError("Could not download TMDb's person export; nothing was deleted")
    popularity = {}
    with gzip.open(io.BytesIO(r.content), "rt", encoding="utf-8") as fh:
        for line in fh:
            p = json.loads(line)
            popularity[p["id"]] = p.get("popularity") or 0.0
    return popularity


async def prune_actors(apply: bool = False) -> dict:
    db = get_db()
    relevance, linked = await _actor_relevance()
    person_popularity = await _person_popularity()

    def keep(doc) -> bool:
        votes, title_popularity = relevance.get(doc["_id"], (0, 0))
        try:
            own = person_popularity.get(int(doc.get("tmdb_id")), 0.0)
        except (TypeError, ValueError):
            own = 0.0
        return (
            (doc.get("source_metadata") or {}).get("source") == "manual"
            or votes >= BIG_TITLE_VOTES
            or title_popularity >= POPULAR_TITLE
            or own >= POPULAR_PERSON
        )

    prune = {
        d["_id"]: d.get("name")
        async for d in db.actors.find({}, {"name": 1, "tmdb_id": 1, "source_metadata.source": 1})
        if not keep(d)
    }
    stats = {"actors_total": await db.actors.count_documents({}), "actors_to_delete": len(prune)}
    stats["actors_kept"] = stats["actors_total"] - stats["actors_to_delete"]
    if not apply or not prune:
        return stats

    # Back up, delete, then drop them from cast/crew lists.
    ids = list(prune)
    stats["backup"] = _backup("actors", await db.actors.find({"_id": {"$in": ids}}).to_list(None))
    deleted = 0
    for i in range(0, len(ids), DELETE_BATCH):
        batch = ids[i:i + DELETE_BATCH]
        for attempt in range(4):  # Atlas free tier throttles and may drop a long operation
            try:
                deleted += (await db.actors.delete_many({"_id": {"$in": batch}})).deleted_count
                break
            except PyMongoError:
                if attempt == 3:
                    raise
                await asyncio.sleep(5 * (attempt + 1))
    stats["actors_deleted"] = deleted
    stats.update(await remove_orphan_people(apply=True))
    return stats


async def remove_orphan_people(apply: bool = False) -> dict:
    """Drop cast/crew entries whose actor no longer exists (pruned or deleted).
    Plain-string legacy entries and entries without an actor_id are left alone."""
    db = get_db()
    existing = {d["_id"] async for d in db.actors.find({}, {"_id": 1})}
    removed, ops_total, backup = 0, 0, []
    for col in TITLE_COLLECTIONS:
        ops = []
        async for doc in db[col].find({}, {f: 1 for f in PEOPLE_FIELDS}):
            changes = {}
            for f in PEOPLE_FIELDS:
                entries = doc.get(f) or []
                keep = [e for e in entries if not (isinstance(e, dict) and e.get("actor_id") and e["actor_id"] not in existing)]
                if len(keep) != len(entries):
                    changes[f] = keep
                    gone = [e for e in entries if e not in keep]
                    removed += len(gone)
                    backup.append({"collection": col, "title_id": doc["_id"], "field": f, "entries": gone})
            if changes:
                ops.append(UpdateOne({"_id": doc["_id"]}, {"$set": changes}))
        ops_total += len(ops)
        if apply:
            for i in range(0, len(ops), NAME_COPY_BATCH):
                await db[col].bulk_write(ops[i:i + NAME_COPY_BATCH], ordered=False)
    stats = {"cast_entries_removed": removed, "titles_changed": ops_total}
    if apply and backup:
        stats["cast_backup"] = _backup("cast_entries", backup)
    return stats
