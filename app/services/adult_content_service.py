"""Find and remove adult (18+) titles (rules: app/domain/media/adult.py).

Titles are soft-deleted and marked `is_adult`, not hard-deleted: the importers treat
any stored TMDb/AniList id (deleted or not) as "already have it", so a removed title
is never re-imported. Anything pointing at a removed title is cleaned up.

Runs weekly (news_scheduler) because AniList/TMDb re-rate titles after import, and
on demand via app/scripts/remove_adult_content.py.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone

import httpx
from bson import json_util

from app.backend.ingestion.tmdb_client import _get as tmdb_get
from app.db.mongo import get_db
from app.domain.media.adult import ADULT_TMDB_KEYWORDS, MAINSTREAM_MIN_VOTES, REMOVED_REASON

logger = logging.getLogger(__name__)

CONTENT_TYPE = {"movies": "movie", "tv_series": "tv_series", "anime": "anime", "manga": "manga"}
PAIR_COLLECTIONS = ("trending", "trending_mentions", "ratings", "watchlist", "comments", "search_logs")
ANILIST_URL = "https://graphql.anilist.co"
ANILIST_QUERY = """query ($ids: [Int], $type: MediaType) {
  Page(perPage: 50) { media(id_in: $ids, type: $type) { id isAdult genres } } }"""


# ── Detection ────────────────────────────────────────────────────────────────


async def _tmdb_ids_with_keyword(kind: str, keyword_id: int) -> set[int]:
    ids, page = set(), 1
    while True:
        r = await tmdb_get(f"/discover/{kind}", {"with_keywords": str(keyword_id), "page": page, "include_adult": "true"})
        if not r:
            break
        ids |= {x["id"] for x in r.get("results", [])}
        if page >= min(r.get("total_pages", 1), 500):
            break
        page += 1
    return ids


async def find_tmdb_adult(collection: str) -> list[dict]:
    """Stored TMDb titles tagged with an adult keyword (and not a well-known film)."""
    kind = "movie" if collection == "movies" else "tv"
    tagged: dict[int, list[str]] = {}
    for keyword_id, name in ADULT_TMDB_KEYWORDS.items():
        for tmdb_id in await _tmdb_ids_with_keyword(kind, keyword_id):
            tagged.setdefault(tmdb_id, []).append(name)

    found = []
    cursor = get_db()[collection].find(
        {"source_metadata.tmdb_id": {"$in": list(tagged)}, "is_adult": {"$ne": True}},
        {"title": 1, "source_metadata.tmdb_id": 1, "rating.tmdb_vote_count": 1},
    )
    async for d in cursor:
        votes = int((d.get("rating") or {}).get("tmdb_vote_count") or 0)
        if votes < MAINSTREAM_MIN_VOTES:
            found.append({"id": d["_id"], "title": d.get("title"), "reason": tagged[d["source_metadata"]["tmdb_id"]]})
    return found


async def find_anilist_adult(collection: str) -> list[dict]:
    """Stored anime/manga that AniList flags as adult or Hentai."""
    path = "source_metadata.anilist_id" if collection == "anime" else "source_metadata.anilist.id"
    media_type = "ANIME" if collection == "anime" else "MANGA"
    docs = await get_db()[collection].find(
        {path: {"$type": "number"}, "is_adult": {"$ne": True}},
        {"title": 1, "name": 1, "source_metadata": 1},
    ).to_list(None)

    def anilist_id(d):
        sm = d.get("source_metadata") or {}
        return sm.get("anilist_id") if collection == "anime" else (sm.get("anilist") or {}).get("id")

    by_id = {anilist_id(d): d for d in docs}
    ids, found = list(by_id), []
    async with httpx.AsyncClient(timeout=30) as http:
        for i in range(0, len(ids), 50):
            r = None
            for attempt in range(5):
                try:
                    r = await http.post(ANILIST_URL, json={"query": ANILIST_QUERY, "variables": {"ids": ids[i:i + 50], "type": media_type}})
                except httpx.TransportError:  # dropped connection: back off and retry
                    await asyncio.sleep(5 * (attempt + 1))
                    continue
                if r.status_code == 429:  # AniList rate limit
                    await asyncio.sleep(int(r.headers.get("Retry-After", 60)))
                    continue
                break
            if r is None or r.status_code != 200:
                # Never remove anything based on a partial answer: fail the whole run.
                raise RuntimeError(f"AniList check failed for {collection} batch {i // 50}")
            for m in ((r.json().get("data") or {}).get("Page") or {}).get("media", []):
                if m.get("isAdult") or "Hentai" in (m.get("genres") or []):
                    d = by_id[m["id"]]
                    title = d.get("name") or (d.get("title") or {}).get("english") or (d.get("title") or {}).get("romaji")
                    found.append({"id": d["_id"], "title": title, "reason": ["anilist isAdult"]})
            await asyncio.sleep(0.8)
    return found


async def find_all() -> dict[str, list[dict]]:
    return {
        "movies": await find_tmdb_adult("movies"),
        "tv_series": await find_tmdb_adult("tv_series"),
        "anime": await find_anilist_adult("anime"),
        "manga": await find_anilist_adult("manga"),
    }


# ── Removal ──────────────────────────────────────────────────────────────────


async def remove(found: dict[str, list[dict]], backup_dir: str | None = "backups") -> dict:
    """Soft-delete the titles and clean up everything that references them."""
    db = get_db()
    now = datetime.now(timezone.utc)
    stats: dict = {}
    backup: dict = {"removed_at": now.isoformat(), "titles": {}, "deleted": {}, "changed": {}}

    for collection, items in found.items():
        ids = [x["id"] for x in items]
        if not ids:
            continue
        backup["titles"][collection] = await db[collection].find({"_id": {"$in": ids}}).to_list(None)

    if backup_dir:  # write the backup before changing anything
        os.makedirs(backup_dir, exist_ok=True)
        path = os.path.join(backup_dir, f"adult_removal_{now:%Y%m%d_%H%M%S}.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json_util.dumps(backup, indent=1))
        stats["backup"] = path

    async def delete_where(col: str, flt: dict, key: str):
        docs = await db[col].find(flt).to_list(None)
        if docs:
            backup["deleted"].setdefault(col, []).extend(docs)
            await db[col].delete_many({"_id": {"$in": [d["_id"] for d in docs]}})
        stats[key] = stats.get(key, 0) + len(docs)

    async def soft_delete_where(col: str, flt: dict, key: str):
        res = await db[col].update_many(
            {**flt, "is_deleted": {"$ne": True}},
            {"$set": {"is_deleted": True, "deleted_at": now, "removed_reason": REMOVED_REASON}},
        )
        stats[key] = stats.get(key, 0) + res.modified_count

    for collection, items in found.items():
        ids = [x["id"] for x in items]
        if not ids:
            continue
        res = await db[collection].update_many(
            {"_id": {"$in": ids}},
            {"$set": {"is_deleted": True, "deleted_at": now, "is_adult": True, "removed_reason": REMOVED_REASON}},
        )
        stats[f"{collection}_removed"] = res.modified_count

        ctype = CONTENT_TYPE[collection]
        for col in PAIR_COLLECTIONS:
            await delete_where(col, {"content_type": ctype, "content_id": {"$in": ids}}, f"{col}_deleted")
        await delete_where("relationships", {"$or": [{"source_id": {"$in": ids}}, {"target_id": {"$in": ids}}]}, "relationships_deleted")
        await delete_where("lore_chunks", {"series_id": {"$in": ids}}, "lore_chunks_deleted")

        if collection in ("anime", "manga"):
            parent = "anime_id" if collection == "anime" else "manga_id"
            child = "episodes" if collection == "anime" else "chapters"
            await soft_delete_where("events", {parent: {"$in": ids}}, "events_removed")
            await soft_delete_where(child, {parent: {"$in": ids}}, f"{child}_removed")

            # Characters: unlink; remove the ones left with no show at all.
            link = "anime_ids" if collection == "anime" else "manga_ids"
            affected = await db.characters.find({link: {"$in": ids}}, {"_id": 1}).to_list(None)
            affected_ids = [c["_id"] for c in affected]
            await db.characters.update_many({link: {"$in": ids}}, {"$pull": {link: {"$in": ids}}})
            orphans = await db.characters.find(
                {"_id": {"$in": affected_ids}, "anime_ids": {"$in": [[], None]}, "manga_ids": {"$in": [[], None]}},
                {"_id": 1},
            ).to_list(None)
            orphan_ids = [c["_id"] for c in orphans]
            backup["changed"].setdefault("characters_unlinked", []).extend(affected_ids)
            if orphan_ids:
                await soft_delete_where("characters", {"_id": {"$in": orphan_ids}}, "characters_removed")
                await delete_where("relationships", {"$or": [{"source_id": {"$in": orphan_ids}}, {"target_id": {"$in": orphan_ids}}]}, "relationships_deleted")
            await db.organizations.update_many({link: {"$in": ids}}, {"$pull": {link: {"$in": ids}}})

    if backup_dir:  # rewrite with the deleted dependents included
        with open(stats["backup"], "w", encoding="utf-8") as fh:
            fh.write(json_util.dumps(backup, indent=1))
    logger.info("adult content removal: %s", stats)
    return stats
