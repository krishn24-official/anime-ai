"""
anilist_resolvers.py — shared upsert helpers for AniList ingestion
===================================================================
Used by fetch_character.py, fetch_character_by_name.py, and fetch_all.py
so that the dedup logic lives in exactly ONE place.

Character dedup strategy (in priority order)
---------------------------------------------
1. Primary  : look up by source_metadata.anilist_id  (the authoritative, immutable key)
              If found → update that exact document (merge anime_ids, voice_actor_ids).
2. Fallback : only for characters that have NO anilist_id at all (manual admin entries).
              Match on name + birth_day + birth_month.
              If both the incoming and the existing character lack a birthdate,
              do NOT merge — create a new document to avoid silent overwrite.
3. Create   : all other cases.  If the name-slug _id is already taken by a DIFFERENT
              character, append _{anilist_id} to produce a unique _id.

Voice-actor dedup strategy
--------------------------
Look up by source_metadata.anilist.id first; create new only if not found.
This matches the pattern already established in fetch_all.py.
"""

import logging
from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from app.db.mongo import get_db
from app.backend.utils.slug import create_slug
from app.backend.transformers.voice_actor_transformer import transform_voice_actor
from app.backend.transformers.character_transformer import transform_character

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Voice-Actor resolver
# ─────────────────────────────────────────────────────────────────────────────

async def resolve_or_create_voice_actor(va_data: dict) -> str | None:
    """
    Resolve a voice_actor _id from AniList staff data.

    Primary lookup: source_metadata.anilist.id  (stable AniList staff id).
    Creates a new document only if no match is found.

    Returns the _id string, or None if va_data is unusable.
    """
    if not va_data:
        return None

    anilist_staff_id = va_data.get("id")
    if not anilist_staff_id:
        return None

    db = get_db()

    # 1. Primary: look up by AniList staff id
    existing = await db["voice_actors"].find_one(
        {"source_metadata.anilist.id": anilist_staff_id}
    )
    if existing:
        return str(existing["_id"])

    # 2. Not found — create new document
    name = va_data.get("name", {}).get("full")
    if not name:
        return None

    slug = create_slug(name)
    if not slug:
        slug = f"va-anilist-{anilist_staff_id}"

    base_id = f"va_{slug}"
    va_id = base_id
    counter = 1

    # Find a unique _id (handle race-condition retries)
    while True:
        if not await db["voice_actors"].find_one({"_id": va_id}):
            break
        va_id = f"{base_id}_{counter}"
        counter += 1

    doc = transform_voice_actor(va_data)
    doc["_id"] = va_id

    try:
        await db["voice_actors"].insert_one(doc)
        logger.debug("Created voice actor: %s (%s)", name, va_id)
    except DuplicateKeyError:
        # Concurrent insert — re-query
        existing = await db["voice_actors"].find_one(
            {"source_metadata.anilist.id": anilist_staff_id}
        )
        if existing:
            return str(existing["_id"])
        # Extremely unlikely second collision; fall through and return va_id anyway
        logger.warning("DuplicateKeyError on voice actor %s — falling back to %s", name, va_id)

    return va_id


# ─────────────────────────────────────────────────────────────────────────────
# Character resolver
# ─────────────────────────────────────────────────────────────────────────────

async def resolve_or_create_character(
    char_node: dict,
    anime_id: str,
    role: str,
    voice_actor_ids: list[str] | None = None,
) -> str | None:
    """
    Resolve (or create) a character document for one AniList character node.

    Parameters
    ----------
    char_node       : raw AniList character node dict (must contain 'id' and 'name.full')
    anime_id        : the DB _id of the anime this character appears in
    role            : AniList role string ('MAIN', 'SUPPORTING', 'BACKGROUND')
    voice_actor_ids : list of already-resolved voice_actor _id strings to attach

    Returns the character's DB _id, or None on failure.

    Dedup strategy (see module docstring for full explanation):
    - Primary   : match on source_metadata.anilist_id
    - Fallback  : name + birth_day + birth_month (manual-admin characters only)
    - Otherwise : create new document
    """
    if not char_node:
        return None

    name = char_node.get("name", {}).get("full")
    if not name:
        return None

    anilist_char_id: int | None = char_node.get("id")
    voice_actor_ids = voice_actor_ids or []

    db = get_db()
    char_collection = db["characters"]

    # ── 1. Primary dedup: look up by AniList character id ─────────────────────
    if anilist_char_id:
        existing = await char_collection.find_one(
            {"source_metadata.anilist_id": anilist_char_id, "is_deleted": {"$ne": True}}
        )
        if existing:
            # Update the existing document — merge anime_ids and voice_actor_ids
            existing_id = existing["_id"]
            merged_anime_ids = list(
                set(existing.get("anime_ids", []) + ([anime_id] if anime_id else []))
            )
            merged_va_ids = list(
                set(existing.get("voice_actor_ids", []) + voice_actor_ids)
            )
            await char_collection.update_one(
                {"_id": existing_id},
                {"$set": {
                    "anime_ids": merged_anime_ids,
                    "voice_actor_ids": merged_va_ids,
                }}
            )
            logger.debug("Updated existing character %s (anilist_id=%s)", name, anilist_char_id)
            return existing_id

    # ── 2. Fallback dedup (manual-admin characters only) ──────────────────────
    # Only attempt if this incoming character has NO anilist_id (admin-created).
    # If both the existing doc and the incoming lack a birthdate → create new (safer).
    if not anilist_char_id:
        incoming_birth_day = (char_node.get("dateOfBirth") or {}).get("day")
        incoming_birth_month = (char_node.get("dateOfBirth") or {}).get("month")

        if incoming_birth_day is not None and incoming_birth_month is not None:
            # Has a birthdate — try to find an existing doc with matching name + birthday
            name_lower = name.strip().lower()
            candidates = await char_collection.find(
                {
                    "is_deleted": {"$ne": True},
                    "source_metadata.anilist_id": {"$exists": False},
                    "birth_day": incoming_birth_day,
                    "birth_month": incoming_birth_month,
                }
            ).to_list(length=20)

            for candidate in candidates:
                if candidate.get("name", "").strip().lower() == name_lower:
                    # Match found — update
                    existing_id = candidate["_id"]
                    merged_anime_ids = list(
                        set(candidate.get("anime_ids", []) + ([anime_id] if anime_id else []))
                    )
                    merged_va_ids = list(
                        set(candidate.get("voice_actor_ids", []) + voice_actor_ids)
                    )
                    await char_collection.update_one(
                        {"_id": existing_id},
                        {"$set": {
                            "anime_ids": merged_anime_ids,
                            "voice_actor_ids": merged_va_ids,
                        }}
                    )
                    logger.debug(
                        "Fallback-matched manual character %s by name+birthday", name
                    )
                    return existing_id

        # Either no birthdate on the incoming character, or no birthday-match found.
        # Fall through to create a new document.

    # ── 3. Create new character document ──────────────────────────────────────
    char_doc = transform_character(char_node, anime_id, role)
    char_doc["voice_actor_ids"] = voice_actor_ids

    # Ensure a unique _id: if the name-slug _id is already occupied by a DIFFERENT
    # character (i.e. a real name collision), append the anilist_id as a disambiguator.
    base_id = char_doc["_id"]  # e.g. "char_kohaku"
    candidate_id = base_id

    existing_by_slug = await char_collection.find_one({"_id": candidate_id})
    if existing_by_slug:
        # The slug is taken by a DIFFERENT character (different anilist_id or manual).
        if anilist_char_id:
            candidate_id = f"{base_id}_{anilist_char_id}"
        else:
            # No anilist_id and slug taken — use a small counter suffix
            counter = 2
            while await char_collection.find_one({"_id": f"{base_id}_{counter}"}):
                counter += 1
            candidate_id = f"{base_id}_{counter}"

    char_doc["_id"] = candidate_id

    try:
        await char_collection.insert_one(char_doc)
        logger.debug("Created new character %s → %s", name, candidate_id)
    except DuplicateKeyError:
        # Concurrent insert — re-check by anilist_id
        if anilist_char_id:
            existing = await char_collection.find_one(
                {"source_metadata.anilist_id": anilist_char_id}
            )
            if existing:
                return str(existing["_id"])
        logger.warning("DuplicateKeyError creating character %s (%s)", name, candidate_id)

    return candidate_id
