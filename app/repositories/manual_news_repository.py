from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId

from app.db.mongo import get_db


def _to_oid(value: str) -> ObjectId | None:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None


async def create_manual_news(doc: dict) -> dict:
    db = get_db()
    doc["created_at"] = datetime.now(timezone.utc)
    doc["updated_at"] = doc["created_at"]
    doc["published_at"] = doc["created_at"]
    doc["source"] = "manual"
    result = await db["news"].insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def get_manual_news_by_id(news_id: str):
    db = get_db()
    oid = _to_oid(news_id)
    if not oid:
        return None
    return await db["news"].find_one({"_id": oid, "source": "manual"})


async def update_manual_news(news_id: str, updates: dict):
    db = get_db()
    oid = _to_oid(news_id)
    if not oid:
        return None
    updates["updated_at"] = datetime.now(timezone.utc)
    result = await db["news"].find_one_and_update(
        {"_id": oid, "source": "manual"},
        {"$set": updates},
        return_document=True,
    )
    return result


async def delete_manual_news(news_id: str) -> bool:
    db = get_db()
    oid = _to_oid(news_id)
    if not oid:
        return False
    result = await db["news"].delete_one({"_id": oid, "source": "manual"})
    return result.deleted_count > 0