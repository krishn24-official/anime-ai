"""Keeps TMDb-sourced movies and TV series up to date after their first import.

Titles were fetched once and never refreshed, so upcoming titles (imported before
their trailers existed) never got trailers, posters, or corrected release dates.

Each run refreshes up to `limit` titles per kind, in priority order:
  1. active titles (releasing in the future or within ACTIVE_DAYS), every ACTIVE_RESYNC_DAYS
  2. all other TMDb titles: once, then every IDLE_RESYNC_DAYS
Never overwrites trailers an admin typed in, or images that are not TMDb's.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.backend.ingestion.tmdb_client import get_movie_details, get_tv_details
from app.backend.ingestion.tmdb_mapper import (
    _extract_us_theatrical_release_date,
    extract_videos,
    image_url,
)
from app.db.mongo import get_db
from app.domain.media.videos import has_manual_trailers

logger = logging.getLogger(__name__)

ACTIVE_DAYS = 180
ACTIVE_RESYNC_DAYS = 7
IDLE_RESYNC_DAYS = 90
CONCURRENCY = 4
SYNCED_AT = "source_metadata.videos_synced_at"

KINDS = {
    "movie": {"collection": "movies", "fetch": get_movie_details},
    "tv": {"collection": "tv_series", "fetch": get_tv_details},
}


def _active_filter(kind: str, now: datetime) -> dict:
    cutoff = (now - timedelta(days=ACTIVE_DAYS)).strftime("%Y-%m-%d")
    if kind == "movie":
        return {"$or": [{"release_date": {"$gte": cutoff}}, {"release_date": None}, {"release_date": {"$exists": False}}]}
    return {"$or": [
        {"first_air_date": {"$gte": cutoff}},
        {"last_air_date": {"$gte": cutoff}},
        {"status": {"$in": ["Returning Series", "In Production", "Planned"]}},
    ]}


def _due_before(days: int, now: datetime) -> dict:
    return {"$or": [{SYNCED_AT: {"$exists": False}}, {SYNCED_AT: {"$lt": now - timedelta(days=days)}}]}


async def find_candidates(kind: str, limit: int, now: datetime, active_only: bool = False) -> list[dict]:
    col = get_db()[KINDS[kind]["collection"]]
    base = {
        "is_deleted": {"$ne": True},
        "source_metadata.tmdb_id": {"$type": "number"},
        "trailers_manual": {"$ne": True},
    }
    projection = {"source_metadata": 1, "trailers": 1, "images": 1, "release_date": 1, "title": 1}
    active = await col.find(
        {"$and": [base, _active_filter(kind, now), _due_before(ACTIVE_RESYNC_DAYS, now)]}, projection
    ).limit(limit).to_list(None)
    picked = {d["_id"] for d in active}
    rest = []
    if len(active) < limit and not active_only:
        rest = await col.find(
            {"$and": [base, {"_id": {"$nin": list(picked)}}, _due_before(IDLE_RESYNC_DAYS, now)]}, projection
        ).limit(limit - len(active)).to_list(None)
    return active + rest


def _is_tmdb_image(url) -> bool:
    return not url or "image.tmdb.org" in str(url)


def build_updates(kind: str, doc: dict, details: dict, now: datetime) -> dict:
    """$set fields for one title from fresh TMDb details."""
    updates: dict = {SYNCED_AT: now}

    if has_manual_trailers(doc.get("trailers")):
        updates["trailers_manual"] = True  # admin-entered: keep them, stop checking
    else:
        updates.update(extract_videos(details))

    images = doc.get("images") or {}
    for field, path, size in (("poster", "poster_path", "w500"), ("backdrop", "backdrop_path", "w1280")):
        fresh = image_url(details.get(path), size) if details.get(path) else None
        if fresh and _is_tmdb_image(images.get(field)) and fresh != images.get(field):
            updates[f"images.{field}"] = fresh

    if details.get("status"):
        updates["status"] = details["status"]

    if kind == "movie":
        today = now.strftime("%Y-%m-%d")
        stored = doc.get("release_date")
        fresh_date = _extract_us_theatrical_release_date(details)
        # Upcoming dates shift; released ones are left alone.
        if fresh_date and (not stored or stored >= today) and fresh_date != stored:
            updates["release_date"] = fresh_date
            updates["year"] = fresh_date[:4]
    else:
        for field in ("first_air_date", "last_air_date"):
            if details.get(field):
                updates[field] = details[field]
        if details.get("number_of_seasons"):
            updates["total_seasons"] = details["number_of_seasons"]
        if details.get("number_of_episodes"):
            updates["total_episodes"] = details["number_of_episodes"]
    return updates


async def refresh(kind: str, limit: int, dry_run: bool = False, active_only: bool = False) -> dict:
    now = datetime.now(timezone.utc)
    col = get_db()[KINDS[kind]["collection"]]
    fetch = KINDS[kind]["fetch"]
    candidates = await find_candidates(kind, limit, now, active_only)
    stats = {"checked": 0, "updated_videos": 0, "gained_trailer": 0, "manual_kept": 0, "failed": 0}
    sem = asyncio.Semaphore(CONCURRENCY)

    async def one(doc: dict):
        async with sem:
            details = await fetch(doc["source_metadata"]["tmdb_id"])
        stats["checked"] += 1
        if not details:
            stats["failed"] += 1
            if not dry_run:  # don't retry a broken/removed id every run
                await col.update_one({"_id": doc["_id"]}, {"$set": {SYNCED_AT: now}})
            return
        updates = build_updates(kind, doc, details, now)
        if updates.get("trailers_manual"):
            stats["manual_kept"] += 1
        elif "trailers" in updates:
            stats["updated_videos"] += 1
            if updates["trailers"] and not doc.get("trailers"):
                stats["gained_trailer"] += 1
        if not dry_run:
            await col.update_one({"_id": doc["_id"]}, {"$set": updates})

    await asyncio.gather(*(one(d) for d in candidates))
    logger.info("tmdb refresh %s: %s", kind, stats)
    return {"candidates": len(candidates), **stats}
