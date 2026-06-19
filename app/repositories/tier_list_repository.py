from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId

from app.db.mongo import get_db


def _to_oid(value: str) -> ObjectId | None:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None


async def create_tier_list(user_id: ObjectId, doc: dict) -> dict:
    db = get_db()
    now = datetime.now(timezone.utc)
    doc["user_id"] = user_id
    doc["created_at"] = now
    doc["updated_at"] = now
    result = await db["tier_lists"].insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def get_tier_list_by_id(tier_list_id: str):
    db = get_db()
    oid = _to_oid(tier_list_id)
    if not oid:
        return None
    return await db["tier_lists"].find_one({"_id": oid})


async def get_user_tier_lists(user_id: ObjectId):
    db = get_db()
    return await (
        db["tier_lists"]
        .find({"user_id": user_id})
        .sort("updated_at", -1)
        .to_list(None)
    )


async def get_public_tier_lists(page: int = 1, limit: int = 20):
    db = get_db()
    skip = (page - 1) * limit
    items = await (
        db["tier_lists"]
        .find({"is_public": True})
        .sort("updated_at", -1)
        .skip(skip)
        .limit(limit)
        .to_list(None)
    )
    total = await db["tier_lists"].count_documents({"is_public": True})
    return items, total


async def update_tier_list(tier_list_id: str, user_id: ObjectId, updates: dict):
    db = get_db()
    oid = _to_oid(tier_list_id)
    if not oid:
        return None
    updates["updated_at"] = datetime.now(timezone.utc)
    result = await db["tier_lists"].find_one_and_update(
        {"_id": oid, "user_id": user_id},
        {"$set": updates},
        return_document=True,
    )
    return result


async def delete_tier_list(tier_list_id: str, user_id: ObjectId) -> bool:
    db = get_db()
    oid = _to_oid(tier_list_id)
    if not oid:
        return False
    result = await db["tier_lists"].delete_one(
        {"_id": oid, "user_id": user_id}
    )
    return result.deleted_count > 0