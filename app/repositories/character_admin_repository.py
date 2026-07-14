from datetime import datetime, timezone
import re
from app.db.mongo import get_db

async def find_character_by_slug(slug: str):
    db = get_db()
    return await db["characters"].find_one({"_id": f"char_{slug}"})

async def create_character(doc: dict):
    db = get_db()
    await db["characters"].insert_one(doc)

async def update_character(content_id: str, updates: dict):
    db = get_db()
    if updates:
        await db["characters"].update_one(
            {"_id": content_id},
            {"$set": updates}
        )

async def soft_delete_character(content_id: str):
    db = get_db()
    await db["characters"].update_one(
        {"_id": content_id},
        {"$set": {
            "is_deleted": True,
            "deleted_at": datetime.now(timezone.utc)
        }}
    )

async def list_characters_for_admin(
    include_deleted: bool = False,
    search: str = None,
    limit: int = 50,
    skip: int = 0
):
    db = get_db()
    query = {}
    
    if not include_deleted:
        query["is_deleted"] = False
        
    if search:
        search_regex = {"$regex": re.compile(search, re.IGNORECASE)}
        query["$or"] = [
            {"name": search_regex},
            {"native_name": search_regex}
        ]
        
    cursor = db["characters"].find(query).sort("name", 1).skip(skip).limit(limit)
    items = await cursor.to_list(length=limit)
    total = await db["characters"].count_documents(query)
    
    return items, total
