from typing import Dict, Any, List, Optional
from datetime import datetime
from app.db.mongo import get_db

async def find_chapter(
    manga_id: str, 
    chapter_number: int
) -> Optional[Dict[str, Any]]:
    db = get_db()
    
    query = {
        "manga_id": manga_id,
        "chapter_number": chapter_number
    }
        
    return await db["chapters"].find_one(query)

async def create_chapter(doc: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    await db["chapters"].insert_one(doc)
    return doc

async def update_chapter(content_id: str, updates: Dict[str, Any]) -> bool:
    db = get_db()
    if not updates:
        return True
        
    result = await db["chapters"].update_one(
        {"_id": content_id},
        {"$set": updates}
    )
    return result.modified_count > 0 or result.matched_count > 0

async def soft_delete_chapter(content_id: str) -> bool:
    db = get_db()
    result = await db["chapters"].update_one(
        {"_id": content_id},
        {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
    )
    return result.modified_count > 0 or result.matched_count > 0

async def list_chapters_for_admin(manga_id: str, include_deleted: bool = False) -> List[Dict[str, Any]]:
    db = get_db()
    query = {"manga_id": manga_id}
    
    if not include_deleted:
        query["is_deleted"] = {"$ne": True}
        
    cursor = db["chapters"].find(query).sort("chapter_number", 1)
    return await cursor.to_list(None)
