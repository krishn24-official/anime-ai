from bson import ObjectId

from app.repositories.tier_list_repository import (
    create_tier_list,
    get_tier_list_by_id,
    get_user_tier_lists,
    get_public_tier_lists,
    update_tier_list,
    delete_tier_list,
)

VALID_CONTENT_TYPES = {"character", "anime", "manga", "movie", "tv_series"}


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


async def create_new_tier_list(
    user_id: ObjectId, name: str, tiers: list, is_public: bool = True
):
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
    """Search characters/anime/manga/movies/tv_series to add to a tier list.

    Uses the shared ranked search (best matches first, up to 5 per type).
    """
    import asyncio

    from app.container import search_service
    from app.domain.search.entities import KIND_BY_CONTENT_TYPE

    if not query or len(query) < 2:
        return []

    types_to_search = (
        [content_type]
        if content_type and content_type in VALID_CONTENT_TYPES
        else sorted(VALID_CONTENT_TYPES)
    )
    pages = await asyncio.gather(
        *(
            search_service().search_kind(query, KIND_BY_CONTENT_TYPE[t], limit=5)
            for t in types_to_search
        )
    )
    return [
        {"content_type": t, "content_id": doc.id, "name": doc.title, "image": doc.image}
        for t, (docs, _) in zip(types_to_search, pages)
        for doc in docs
    ]

