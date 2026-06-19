from bson import ObjectId

from app.services.content_types import (
    is_valid_content_type,
    to_object_id,
    CONTENT_COLLECTION_MAP,
)
from app.services.rating_scale import RATING_SCALE, is_valid_rating
from app.db.mongo import get_db

from app.repositories.rating_repository import (
    upsert_rating,
    get_user_rating,
    get_rating_stats,
    delete_rating,
)
from app.repositories.watchlist_repository import (
    add_to_watchlist,
    remove_from_watchlist,
    is_in_watchlist,
    get_user_watchlist,
)
from app.repositories.comment_repository import (
    create_comment,
    get_comments_for_content,
    get_comment_by_id,
    delete_comment,
)


class ContentError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


async def _ensure_content_exists(content_type: str, content_id: str):
    db = get_db()
    collection = CONTENT_COLLECTION_MAP[content_type]

    # content_id is a custom string id (e.g. "anime_naruto"), not an ObjectId
    exists = await db[collection].find_one({"_id": content_id}, {"_id": 1})

    if not exists:
        raise ContentError(404, f"{content_type} not found")


def _validate(content_type: str, content_id: str) -> str:
    if not is_valid_content_type(content_type):
        raise ContentError(400, f"Invalid content_type: {content_type}")

    if not content_id or not content_id.strip():
        raise ContentError(400, "content_id cannot be empty")

    return content_id


# --- Ratings ---

async def rate_content(user_id: ObjectId, content_type: str, content_id: str, rating: str):
    if not is_valid_rating(rating):
        raise ContentError(400, f"Rating must be one of: {', '.join(RATING_SCALE)}")

    content_id = _validate(content_type, content_id)
    await _ensure_content_exists(content_type, content_id)

    await upsert_rating(user_id, content_type, content_id, rating)

    return await get_content_rating(user_id, content_type, content_id)


async def get_content_rating(user_id: ObjectId | None, content_type: str, content_id: str):
    content_id = _validate(content_type, content_id)

    stats = await get_rating_stats(content_type, content_id)

    user_rating = None
    if user_id:
        own = await get_user_rating(user_id, content_type, content_id)
        user_rating = own["rating"] if own else None

    return {
        "average_rating": stats["average_rating"],
        "average_weight": stats["average_weight"],
        "count": stats["count"],
        "user_rating": user_rating,
    }


async def remove_rating(user_id: ObjectId, content_type: str, content_id: str):
    content_id = _validate(content_type, content_id)
    await delete_rating(user_id, content_type, content_id)


# --- Watchlist ---

async def add_watchlist_item(user_id: ObjectId, content_type: str, content_id: str):
    content_id = _validate(content_type, content_id)
    await _ensure_content_exists(content_type, content_id)

    await add_to_watchlist(user_id, content_type, content_id)

    return {"content_type": content_type, "content_id": content_id, "in_watchlist": True}


async def remove_watchlist_item(user_id: ObjectId, content_type: str, content_id: str):
    content_id = _validate(content_type, content_id)

    await remove_from_watchlist(user_id, content_type, content_id)

    return {"content_type": content_type, "content_id": content_id, "in_watchlist": False}


async def check_watchlist_item(user_id: ObjectId, content_type: str, content_id: str):
    content_id = _validate(content_type, content_id)

    in_list = await is_in_watchlist(user_id, content_type, content_id)

    return {"content_type": content_type, "content_id": content_id, "in_watchlist": in_list}


async def fetch_user_watchlist(user_id: ObjectId):
    items = await get_user_watchlist(user_id)

    return [
        {
            "content_type": item["content_type"],
            "content_id": item["content_id"],
            "added_at": item["added_at"],
        }
        for item in items
    ]


# --- Comments ---

def _serialize_comment(comment: dict) -> dict:
    return {
        "id": str(comment["_id"]),
        "user_id": str(comment["user_id"]),
        "display_name": comment.get("display_name"),    # enriched by caller
        "username": comment.get("username"),            # enriched by caller
        "content_type": comment["content_type"],
        "content_id": comment["content_id"],
        "text": comment["text"],
        "parent_id": str(comment["parent_id"]) if comment.get("parent_id") else None,
        "is_public": comment.get("is_public", True),
        "likes": comment.get("likes", 0),
        "created_at": comment["created_at"],
    }


def _build_comment_tree(comments: list[dict]) -> list[dict]:
    by_id = {str(c["_id"]): _serialize_comment(c) for c in comments}

    for comment in by_id.values():
        comment["replies"] = []

    roots = []

    for comment in by_id.values():
        parent_id = comment["parent_id"]

        if parent_id and parent_id in by_id:
            by_id[parent_id]["replies"].append(comment)
        else:
            roots.append(comment)

    return roots


async def add_comment(user_id: ObjectId, content_type: str, content_id: str, text: str, parent_id: str | None = None):
    if not text or not text.strip():
        raise ContentError(400, "Comment text cannot be empty")

    content_id = _validate(content_type, content_id)
    await _ensure_content_exists(content_type, content_id)

    parent_oid = None
    if parent_id:
        parent_oid = to_object_id(parent_id)
        if not parent_oid:
            raise ContentError(400, f"Invalid parent_id: {parent_id}")

        parent_comment = await get_comment_by_id(parent_oid)
        if not parent_comment:
            raise ContentError(404, "Parent comment not found")

    comment = await create_comment(user_id, content_type, content_id, text.strip(), parent_oid)

    return _serialize_comment(comment)


async def fetch_comments(content_type: str, content_id: str):
    content_id = _validate(content_type, content_id)

    comments = await get_comments_for_content(content_type, content_id)

    if not comments:
        return []

    # Batch fetch user display names
    db = get_db()
    user_ids = list({c["user_id"] for c in comments if c.get("user_id")})
    users = await db["users"].find(
        {"_id": {"$in": user_ids}},
        {"_id": 1, "display_name": 1, "username": 1}
    ).to_list(None)
    user_map = {u["_id"]: u for u in users}

    # Enrich comments with user info
    for comment in comments:
        user = user_map.get(comment.get("user_id"), {})
        comment["display_name"] = user.get("display_name")
        comment["username"] = user.get("username")

    return _build_comment_tree(comments)


async def remove_comment(user_id: ObjectId, comment_id: str):
    comment_oid = to_object_id(comment_id)
    if not comment_oid:
        raise ContentError(400, f"Invalid comment_id: {comment_id}")

    comment = await get_comment_by_id(comment_oid)
    if not comment:
        raise ContentError(404, "Comment not found")

    if comment["user_id"] != user_id:
        raise ContentError(403, "You can only delete your own comments")

    await delete_comment(comment_oid)