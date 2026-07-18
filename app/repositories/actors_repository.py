from datetime import datetime, timezone
from app.db.mongo import get_db

async def get_all_actors(include_deleted: bool = False, search: str = None, limit: int = 50, skip: int = 0):
    db = get_db()
    query = {} if include_deleted else {"is_deleted": False}
    
    if search:
        query["name"] = {"$regex": search, "$options": "i"}
        
    cursor = db["actors"].find(query).sort("name", 1).skip(skip).limit(limit)
    items = await cursor.to_list(None)
    total = await db["actors"].count_documents(query)
    
    return {"items": items, "total": total}

async def get_actor_by_id(actor_identifier: str):
    db = get_db()
    # First try by _id
    actor = await db["actors"].find_one({"_id": actor_identifier, "is_deleted": False})
    if actor:
        return actor
    # Fallback to exact name match
    return await db["actors"].find_one({"name": actor_identifier, "is_deleted": False})

async def search_actors(query: str, limit: int = 20):
    db = get_db()
    return await db["actors"].find(
        {
            "name": {"$regex": query, "$options": "i"},
            "is_deleted": False
        },
        {"_id": 1, "name": 1, "images.profile": 1}
    ).limit(limit).to_list(None)

async def create_actor(doc: dict):
    db = get_db()
    await db["actors"].insert_one(doc)
    return doc["_id"]

async def update_actor(actor_id: str, updates: dict):
    db = get_db()
    if not updates:
        return True
    result = await db["actors"].update_one(
        {"_id": actor_id},
        {"$set": updates}
    )
    return result.modified_count > 0

async def soft_delete_actor(actor_id: str):
    db = get_db()
    result = await db["actors"].update_one(
        {"_id": actor_id},
        {
            "$set": {
                "is_deleted": True,
                "deleted_at": datetime.now(timezone.utc)
            }
        }
    )
    return result.modified_count > 0
