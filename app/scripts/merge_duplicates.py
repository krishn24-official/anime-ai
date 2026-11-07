"""Find and merge duplicate records (same AniList/TMDb id, or same natural key).

    python -m app.scripts.merge_duplicates            # DRY RUN: report only, changes nothing
    python -m app.scripts.merge_duplicates --apply    # back up, then merge

What --apply does, per duplicate group:
  1. keeper = record with the shortest _id (the original; copies got "_2" / "_<anilistId>")
  2. keeper gets the copies' missing fields; list fields are combined
  3. every reference to a copy is re-pointed to the keeper (relationships, events,
     cast lists, trending, ratings, ...). Where a unique index would collide, the
     copy's record is removed (the keeper already has the same one)
  4. the copies are deleted
Then duplicate relationships (same source, target, relationship) are removed.

Before changing anything, --apply writes a backup to backups/ with every record it
modifies or deletes and the ids of every re-pointed document.
"""

import argparse
import asyncio
import json
import os
from collections import defaultdict
from datetime import datetime, timezone

from bson import json_util
from pymongo import AsyncMongoClient, UpdateOne
from pymongo.errors import BulkWriteError, DuplicateKeyError

import app.db.mongo as mongo
from app.config import MONGO_URI
from app.db.mongo import get_db
from app.domain.search.rules import normalize

BATCH = 500
BACKUP_DIR = "backups"


def _get(doc, path):
    for part in path.split("."):
        if not isinstance(doc, dict):
            return None
        doc = doc.get(part)
    return doc


def _empty(v):
    return v is None or v == "" or v == [] or v == {}


def merge_into(keeper: dict, other: dict) -> dict:
    """Fields to $set on keeper: fill missing values, combine lists, recurse into dicts."""
    updates = {}
    for key, value in other.items():
        if key == "_id" or _empty(value):
            continue
        current = keeper.get(key)
        if _empty(current):
            updates[key] = value
        elif isinstance(current, list) and isinstance(value, list):
            if all(isinstance(x, (str, int, float)) for x in current + value):
                combined = list(dict.fromkeys(current + value))
                if combined != current:
                    updates[key] = combined
        elif isinstance(current, dict) and isinstance(value, dict):
            nested = merge_into(current, value)
            if nested:
                updates[key] = {**current, **nested}
    return updates


# ── Which records are duplicates ─────────────────────────────────────────────


def _char_anilist(d):
    return _get(d, "source_metadata.anilist.id") or _get(d, "source_metadata.anilist_id")


def _year(d):
    return str(d.get("year") or "")[:4]


# kind -> (collection, external-id function, name key for records missing that id)
ENTITY_RULES = {
    "voice_actors": ("voice_actors", lambda d: _get(d, "source_metadata.anilist.id"), lambda d: normalize(d.get("name") or "")),
    "characters": ("characters", _char_anilist, None),
    "actors": ("actors", lambda d: d.get("tmdb_id"), None),
    "anime": ("anime", lambda d: _get(d, "source_metadata.anilist_id"), None),
    "manga": ("manga", lambda d: _get(d, "source_metadata.anilist.id"), lambda d: normalize(d.get("name") or "")),
    "movies": ("movies", lambda d: _get(d, "source_metadata.tmdb_id"), None),
    "tv_series": ("tv_series", lambda d: _get(d, "source_metadata.tmdb_id"), lambda d: (normalize(d.get("title") or ""), _year(d))),
}

CONTENT_TYPE = {"anime": "anime", "manga": "manga", "movies": "movie", "tv_series": "tv_series"}
PAIR_COLLECTIONS = ["trending", "trending_mentions", "ratings", "watchlist", "comments", "search_logs"]

# References to each kind: (collection, field, how). how: scalar | array | objarray:<subfield>
REFS = {
    "voice_actors": [("characters", "voice_actor_id", "scalar"), ("characters", "voice_actor_ids", "array")],
    "characters": [
        ("relationships", "source_id", "scalar"), ("relationships", "target_id", "scalar"),
        ("events", "character_ids", "array"), ("episodes", "character_ids", "array"),
        ("chapters", "character_ids", "array"), ("chapters", "characters_appeared", "objarray:slug"),
        ("voice_actors", "character_ids", "array"), ("lore_chunks", "character_ids", "array"),
    ],
    "actors": [
        ("movies", "cast", "objarray:actor_id"), ("movies", "director", "objarray:actor_id"),
        ("movies", "writer", "objarray:actor_id"), ("movies", "writers", "objarray:actor_id"),
        ("tv_series", "cast", "objarray:actor_id"), ("tv_series", "creators", "objarray:actor_id"),
    ],
    "anime": [
        ("episodes", "anime_id", "scalar"), ("episodes", "series_id", "scalar"), ("events", "anime_id", "scalar"),
        ("characters", "anime_ids", "array"), ("organizations", "anime_ids", "array"),
        ("anime", "related_anime_ids", "array"), ("lore_chunks", "series_id", "scalar"),
        ("relationships", "source_id", "scalar"), ("relationships", "target_id", "scalar"),
    ],
    "manga": [
        ("chapters", "manga_id", "scalar"), ("chapters", "series_id", "scalar"), ("events", "manga_id", "scalar"),
        ("characters", "manga_ids", "array"), ("organizations", "manga_ids", "array"),
        ("anime", "manga_id", "scalar"), ("lore_chunks", "series_id", "scalar"),
        ("relationships", "source_id", "scalar"), ("relationships", "target_id", "scalar"),
    ],
    "movies": [("lore_chunks", "series_id", "scalar"), ("relationships", "source_id", "scalar"), ("relationships", "target_id", "scalar")],
    "tv_series": [("episodes", "series_id", "scalar"), ("lore_chunks", "series_id", "scalar"),
                  ("relationships", "source_id", "scalar"), ("relationships", "target_id", "scalar")],
}


async def find_entity_groups(db, kind):
    col, ext_fn, name_fn = ENTITY_RULES[kind]
    docs = await db[col].find({"is_deleted": {"$ne": True}}).to_list(None)
    groups = defaultdict(list)
    for d in docs:
        ext = ext_fn(d)
        if ext not in (None, ""):
            groups[("ext", str(ext))].append(d)
    if name_fn:
        # A record missing the external id joins a same-name group of exactly one
        # record that has an id (e.g. a manual "Loki" + the TMDb "Loki").
        by_name = defaultdict(list)
        for d in docs:
            by_name[name_fn(d)].append(d)
        for name, same in by_name.items():
            missing = [d for d in same if ext_fn(d) in (None, "")]
            with_ext = {str(ext_fn(d)) for d in same if ext_fn(d) not in (None, "")}
            if name and missing and len(with_ext) == 1:
                groups[("ext", with_ext.pop())].extend(missing)
    result = []
    for docs_in_group in groups.values():
        if len(docs_in_group) > 1:
            ordered = sorted(docs_in_group, key=lambda d: (len(str(d["_id"])), str(d["_id"])))
            result.append((ordered[0], ordered[1:]))
    return result


# ── Re-pointing references ───────────────────────────────────────────────────


async def plan_refs(db, kind, mapping):
    """{(collection, field): [doc ids referencing a duplicate]}"""
    dup_ids = list(mapping)
    plan = {}
    for col, field, how in REFS.get(kind, []):
        path = field if how in ("scalar", "array") else f"{field}.{how.split(':')[1]}"
        ids = []
        for i in range(0, len(dup_ids), 1000):
            cursor = db[col].find({path: {"$in": dup_ids[i:i + 1000]}}, {"_id": 1})
            ids += [d["_id"] async for d in cursor]
        if ids:
            plan[(col, field, how)] = ids
    if kind in CONTENT_TYPE:
        for col in PAIR_COLLECTIONS:
            cursor = db[col].find({"content_type": CONTENT_TYPE[kind], "content_id": {"$in": dup_ids}}, {"_id": 1})
            ids = [d["_id"] async for d in cursor]
            if ids:
                plan[(col, "content_id", "pair")] = ids
    return plan


def _replace(value, how, mapping):
    if how in ("scalar", "pair"):
        return mapping.get(value, value)
    if how == "array":
        return list(dict.fromkeys(mapping.get(v, v) for v in value or []))
    sub = how.split(":")[1]
    return [
        {**o, sub: mapping.get(o.get(sub), o.get(sub))} if isinstance(o, dict) else o
        for o in value or []
    ]


async def apply_refs(db, plan, mapping, removed_on_conflict):
    for (col, field, how), ids in plan.items():
        for i in range(0, len(ids), BATCH):
            docs = await db[col].find({"_id": {"$in": ids[i:i + BATCH]}}).to_list(None)
            updates = [({"_id": d["_id"]}, {"$set": {field: _replace(d.get(field), how, mapping)}}) for d in docs]
            try:
                await db[col].bulk_write([UpdateOne(f, u) for f, u in updates], ordered=False)
            except BulkWriteError:
                # A unique index collided (the keeper already has this record):
                # retry one by one and drop the duplicate's copy on conflict.
                for d, (f, u) in zip(docs, updates):
                    try:
                        await db[col].update_one(f, u)
                    except DuplicateKeyError:
                        removed_on_conflict.append({"collection": col, "doc": d})
                        await db[col].delete_one({"_id": d["_id"]})


# ── Natural-key duplicates (events, relationships) ───────────────────────────


async def find_key_duplicates(db, col, key_fn):
    groups = defaultdict(list)
    async for d in db[col].find({"is_deleted": {"$ne": True}} if col == "events" else {}):
        k = key_fn(d)
        if k:
            groups[k].append(d)
    # keep the most complete record (most non-empty fields), then shortest id
    return [
        sorted(g, key=lambda d: (-sum(not _empty(v) for v in d.values()), len(str(d["_id"]))))
        for g in groups.values() if len(g) > 1
    ]


def _event_key(e):
    if e.get("manga_id") and e.get("chapter_number") is not None:
        return ("manga", e["manga_id"], e["chapter_number"], e.get("event_type"))
    if e.get("anime_id") and e.get("episode_number") is not None:
        return ("anime", e["anime_id"], e["episode_number"], e.get("event_type"))
    return None


def _relationship_key(r):
    if not r.get("source_id") or not r.get("target_id"):
        return None
    return (r["source_id"], r["target_id"], (r.get("relationship") or "").lower())


# ── Main ─────────────────────────────────────────────────────────────────────


async def run(apply: bool) -> None:
    db = get_db()
    backup = {"started_at": datetime.now(timezone.utc).isoformat(), "entities": {}, "deleted": [], "removed_on_conflict": []}
    work = []

    print(f"{'kind':13} {'groups':>7} {'copies':>7}  references to re-point")
    for kind, (col, _, _) in ENTITY_RULES.items():
        groups = await find_entity_groups(db, kind)
        mapping = {dup["_id"]: keeper["_id"] for keeper, dups in groups for dup in dups}
        plan = await plan_refs(db, kind, mapping) if mapping else {}
        refs = ", ".join(f"{c}.{f}:{len(ids)}" for (c, f, _), ids in plan.items()) or "-"
        print(f"{kind:13} {len(groups):7} {len(mapping):7}  {refs}")
        if groups:
            work.append((kind, col, groups, mapping, plan))

    event_groups = await find_key_duplicates(db, "events", _event_key)
    print(f"{'events':13} {len(event_groups):7} {sum(len(g) - 1 for g in event_groups):7}  -")

    if not apply:
        print("\nDRY RUN: nothing changed. Run with --apply to merge (a backup is written first).")
        print("(Duplicate relationships are counted and removed after characters are merged.)")
        return

    # 1. Backup everything we are about to modify or delete.
    for kind, col, groups, mapping, plan in work:
        backup["entities"][kind] = {
            "collection": col,
            "groups": [{"keeper": k, "duplicates": d} for k, d in groups],
            "repointed": [{"collection": c, "field": f, "ids": ids} for (c, f, _), ids in plan.items()],
            "mapping": mapping,
        }
    backup["events"] = [{"kept": g[0], "deleted": g[1:]} for g in event_groups]
    os.makedirs(BACKUP_DIR, exist_ok=True)
    path = os.path.join(BACKUP_DIR, f"duplicate_merge_{datetime.now():%Y%m%d_%H%M%S}.json")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json_util.dumps(backup, indent=1))
    print(f"\nbackup written: {path}")

    # 2. Merge each kind.
    for kind, col, groups, mapping, plan in work:
        removed = []
        await apply_refs(db, plan, mapping, removed)
        backup["removed_on_conflict"] += removed

        # Compute the keepers' merged fields from the in-memory copies (also in the
        # backup), then delete the copies BEFORE updating the keepers: the copies
        # still hold the external id, so copying it onto a keeper first would
        # violate the unique external-id index.
        keeper_updates = []
        for keeper, dups in groups:
            updates = {}
            for dup in dups:
                updates.update(merge_into({**keeper, **updates}, dup))
            anilist = (
                (_char_anilist(keeper) or _char_anilist({**keeper, **updates}))
                if kind == "characters"
                else None
            )
            if anilist:
                updates["source_metadata"] = {
                    **keeper.get("source_metadata", {}), **updates.get("source_metadata", {}),
                    "anilist_id": anilist, "anilist": {"id": anilist},
                }
            if updates:
                keeper_updates.append((keeper["_id"], updates))

        await db[col].delete_many({"_id": {"$in": list(mapping)}})
        for keeper_id, updates in keeper_updates:
            await db[col].update_one({"_id": keeper_id}, {"$set": updates})
        print(f"{kind:13} merged {len(mapping)} copies; removed {len(removed)} colliding references")

    # 3. Events and relationships (after characters were re-pointed).
    for g in event_groups:
        await db.events.delete_many({"_id": {"$in": [d["_id"] for d in g[1:]]}})
    self_refs = await db.relationships.find({"$expr": {"$eq": ["$source_id", "$target_id"]}}).to_list(None)
    rel_groups = await find_key_duplicates(db, "relationships", _relationship_key)
    rel_deleted = [d for g in rel_groups for d in g[1:]] + self_refs
    if rel_deleted:
        await db.relationships.delete_many({"_id": {"$in": [d["_id"] for d in rel_deleted]}})
    backup["relationships_deleted"] = rel_deleted
    print(f"{'events':13} removed {sum(len(g) - 1 for g in event_groups)}")
    print(f"{'relationships':13} removed {len(rel_deleted)} duplicate/self-referencing")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json_util.dumps(backup, indent=1))
    print(f"backup updated with conflict removals: {path}")


async def main(apply: bool) -> None:
    # Plain client: no startup index maintenance, so a dry run changes nothing.
    mongo.client = AsyncMongoClient(MONGO_URI)
    try:
        await run(apply)
    finally:
        await mongo.client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="merge (default is a dry run)")
    asyncio.run(main(parser.parse_args().apply))
