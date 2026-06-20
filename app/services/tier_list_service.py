from bson import ObjectId

from app.repositories.tier_list_repository import (
    create_tier_list,
    get_tier_list_by_id,
    get_user_tier_lists,
    get_public_tier_lists,
    update_tier_list,
    delete_tier_list,
)
from app.db.mongo import get_db

VALID_CONTENT_TYPES = {"character", "anime", "manga", "movie", "tv_series"}

CONTENT_COLLECTION_MAP = {
    "character": "characters",
    "anime": "anime",
    "manga": "manga",
    "movie": "movies",
    "tv_series": "tv_series",
}


def _serialize(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "user_id": str(doc["user_id"]),
        "name": doc.get("name"),
        "tiers": doc.get("tiers", []),
        "is_public": doc.get("is_public", True),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


def _validate_tiers(tiers: list) -> tuple[bool, str | None]:
    if not isinstance(tiers, list):
        return False, "tiers must be a list"

    if len(tiers) > 20:
        return False, "Maximum 20 tiers allowed"

    for tier in tiers:
        if not isinstance(tier, dict):
            return False, "Each tier must be an object"

        if not tier.get("name"):
            return False, "Each tier must have a name"

        if len(tier["name"]) > 50:
            return False, "Tier name max 50 characters"

        items = tier.get("items", [])
        if not isinstance(items, list):
            return False, "Tier items must be a list"

        for item in items:
            if item.get("content_type") not in VALID_CONTENT_TYPES:
                return False, f"Invalid content_type: {item.get('content_type')}"
            if not item.get("content_id"):
                return False, "Each item must have a content_id"

    return True, None


async def create_new_tier_list(user_id: ObjectId, name: str, tiers: list, is_public: bool = True):
    if not name or not name.strip():
        return None, "Tier list name is required"

    if len(name) > 100:
        return None, "Name max 100 characters"

    valid, error = _validate_tiers(tiers)
    if not valid:
        return None, error

    doc = {
        "name": name.strip(),
        "tiers": tiers,
        "is_public": is_public,
    }

    result = await create_tier_list(user_id, doc)
    return _serialize(result), None


async def fetch_user_tier_lists(user_id: ObjectId):
    items = await get_user_tier_lists(user_id)
    return [_serialize(i) for i in items]


async def fetch_tier_list(tier_list_id: str, current_user_id: ObjectId | None = None):
    doc = await get_tier_list_by_id(tier_list_id)

    if not doc:
        return None, "Tier list not found"

    # Allow access if public or if the owner
    if not doc.get("is_public") and doc.get("user_id") != current_user_id:
        return None, "This tier list is private"

    return _serialize(doc), None


async def fetch_public_tier_lists(page: int = 1, limit: int = 20):
    items, total = await get_public_tier_lists(page=page, limit=limit)
    return {
        "items": [_serialize(i) for i in items],
        "total": total,
        "page": page,
        "limit": limit,
    }


async def update_existing_tier_list(
    tier_list_id: str,
    user_id: ObjectId,
    name: str | None,
    tiers: list | None,
    is_public: bool | None,
):
    updates = {}

    if name is not None:
        if not name.strip():
            return None, "Tier list name cannot be empty"
        if len(name) > 100:
            return None, "Name max 100 characters"
        updates["name"] = name.strip()

    if tiers is not None:
        valid, error = _validate_tiers(tiers)
        if not valid:
            return None, error
        updates["tiers"] = tiers

    if is_public is not None:
        updates["is_public"] = is_public

    if not updates:
        return None, "No fields to update"

    result = await update_tier_list(tier_list_id, user_id, updates)

    if not result:
        return None, "Tier list not found or not authorized"

    return _serialize(result), None


async def delete_existing_tier_list(tier_list_id: str, user_id: ObjectId):
    deleted = await delete_tier_list(tier_list_id, user_id)
    if not deleted:
        return False, "Tier list not found or not authorized"
    return True, None


async def search_content_for_tier_list(query: str, content_type: str | None = None):
    """Search characters/anime/manga/movies/tv_series to add to tier list."""
    if not query or len(query) < 2:
        return []

    db = get_db()
    results = []

    types_to_search = (
        [content_type] if content_type and content_type in VALID_CONTENT_TYPES
        else list(VALID_CONTENT_TYPES)
    )

    for ctype in types_to_search:
        collection = CONTENT_COLLECTION_MAP[ctype]

        # Use title or name field depending on collection
        name_field = "name" if ctype in ("character", "manga") else "title"

        if ctype == "character":
            query_filter = {
                "$or": [
                    {"name": {"$regex": query, "$options": "i"}},
                    {"anime": {"$regex": query, "$options": "i"}},
                    {"manga": {"$regex": query, "$options": "i"}},
                ]
            }
            projection = {"_id": 1, "name": 1, "images": 1}
        elif ctype == "anime":
            query_filter = {
                "$or": [
                    {"title.english": {"$regex": query, "$options": "i"}},
                    {"title.romaji": {"$regex": query, "$options": "i"}},
                ]
            }
            projection = {"_id": 1, "title": 1, "images": 1}
        else:
            query_filter = {name_field: {"$regex": query, "$options": "i"}}
            projection = {"_id": 1, name_field: 1, "images": 1}

        docs = await (
            db[collection]
            .find(query_filter, projection)
            .limit(5)
            .to_list(None)
        )

        for doc in docs:
            images = doc.get("images") or {}

            if ctype == "anime":
                label = (
                    (doc.get("title") or {}).get("english")
                    or (doc.get("title") or {}).get("romaji")
                    or str(doc["_id"])
                )
            else:
                label = doc.get(name_field) or str(doc["_id"])

            results.append({
                "content_type": ctype,
                "content_id": str(doc["_id"]),
                "name": label,
                "image": (
                    images.get("profile")
                    or images.get("poster")
                    or images.get("cover_image")
                ),
            })

    return results