from datetime import datetime, timezone, timedelta
from pymongo.errors import DuplicateKeyError
from app.db.mongo import get_db

async def upsert_trending(
    content_type: str, 
    content_id: str, 
    source: str, 
    reason: str, 
    score: float, 
    pinned: bool = False, 
    set_by: str | None = None, 
    note: str | None = None, 
    expires_at: datetime | None = None,
    custom_poster: str | None = None
) -> bool:
    db = get_db()
    now = datetime.now(timezone.utc)
    
    doc = {
        "content_type": content_type,
        "content_id": content_id,
        "source": source,
        "reason": reason,
        "score": score,
        "pinned": pinned,
        "computed_at": now
    }
    if set_by:
        doc["set_by"] = set_by
    if note:
        doc["note"] = note
    if expires_at:
        doc["expires_at"] = expires_at
    if custom_poster:
        doc["custom_poster"] = custom_poster
        
    if pinned:
        # Pinned entries always overwrite
        await db["trending"].update_one(
            {"content_type": content_type, "content_id": content_id},
            {"$set": doc},
            upsert=True
        )
        return True
    else:
        # Non-pinned only write if no existing pinned entry exists
        existing = await db["trending"].find_one({"content_type": content_type, "content_id": content_id})
        if existing and existing.get("pinned"):
            return False
        
        await db["trending"].update_one(
            {"content_type": content_type, "content_id": content_id},
            {"$set": doc},
            upsert=True
        )
        return True

async def remove_trending(content_type: str, content_id: str):
    db = get_db()
    await db["trending"].delete_one({"content_type": content_type, "content_id": content_id})

async def get_active_trending(limit: int = 10):
    db = get_db()
    now = datetime.now(timezone.utc)
    
    # TTL index will auto-delete expired docs, but we can double check just in case,
    # or just rely on TTL. It's safer to filter if we use aggregate.
    # Actually TTL is not instantaneous, so filter is good.
    pipeline = [
        {"$match": {
            "$or": [
                {"expires_at": {"$exists": False}},
                {"expires_at": None},
                {"expires_at": {"$gt": now}}
            ]
        }},
        {"$sort": {"pinned": -1, "score": -1}},
        {"$limit": limit}
    ]
    
    cursor = await db["trending"].aggregate(pipeline)
    return await cursor.to_list(None)

async def get_trending_entry(content_type: str, content_id: str):
    db = get_db()
    return await db["trending"].find_one({"content_type": content_type, "content_id": content_id})

async def record_mention(content_type: str, content_id: str, news_id: str, matched_alias: str):
    db = get_db()
    try:
        await db["trending_mentions"].insert_one({
            "content_type": content_type,
            "content_id": content_id,
            "news_id": news_id,
            "matched_alias": matched_alias,
            "matched_at": datetime.now(timezone.utc)
        })
    except DuplicateKeyError:
        pass  # Silently ignore if this article already mentioned this content

async def get_mention_counts(hours: int = 48) -> list[dict]:
    db = get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    pipeline = [
        {"$match": {"matched_at": {"$gte": cutoff}}},
        {"$group": {
            "_id": {
                "content_type": "$content_type",
                "content_id": "$content_id"
            },
            "mention_count": {"$sum": 1}
        }},
        {"$project": {
            "_id": 0,
            "content_type": "$_id.content_type",
            "content_id": "$_id.content_id",
            "mention_count": 1
        }}
    ]
    
    cursor = await db["trending_mentions"].aggregate(pipeline)
    return await cursor.to_list(None)

async def record_search_click(content_type: str, content_id: str, query: str, user_id: str):
    db = get_db()
    await db["search_logs"].insert_one({
        "content_type": content_type,
        "content_id": content_id,
        "query": query,
        "user_id": user_id,
        "searched_at": datetime.now(timezone.utc)
    })

async def get_search_counts(hours: int = 3) -> list[dict]:
    db = get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    pipeline = [
        {"$match": {"searched_at": {"$gte": cutoff}}},
        {"$group": {
            "_id": {
                "content_type": "$content_type",
                "content_id": "$content_id"
            },
            "distinct_users": {"$addToSet": "$user_id"}
        }},
        {"$project": {
            "_id": 0,
            "content_type": "$_id.content_type",
            "content_id": "$_id.content_id",
            "distinct_searcher_count": {"$size": "$distinct_users"}
        }}
    ]
    
    cursor = await db["search_logs"].aggregate(pipeline)
    return await cursor.to_list(None)


