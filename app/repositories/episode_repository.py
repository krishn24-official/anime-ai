from typing import Dict, Any, List, Optional
from datetime import datetime
from app.db.mongo import get_db

async def find_episode(
    anime_id: Optional[str] = None, 
    tv_series_id: Optional[str] = None, 
    episode_number: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    db = get_db()
    
    query = {"episode_number": episode_number}
    if anime_id:
        query["anime_id"] = anime_id
    elif tv_series_id:
        query["tv_series_id"] = tv_series_id
        
    return await db["episodes"].find_one(query)

async def create_episode(doc: Dict[str, Any]) -> Dict[str, Any]:
    db = get_db()
    await db["episodes"].insert_one(doc)
    return doc

async def update_episode(content_id: str, updates: Dict[str, Any]) -> bool:
    db = get_db()
    if not updates:
        return True
        
    result = await db["episodes"].update_one(
        {"_id": content_id},
        {"$set": updates}
    )
    return result.modified_count > 0 or result.matched_count > 0

async def soft_delete_episode(content_id: str) -> bool:
    db = get_db()
    result = await db["episodes"].update_one(
        {"_id": content_id},
        {"$set": {"is_deleted": True, "deleted_at": datetime.utcnow()}}
    )
    return result.modified_count > 0 or result.matched_count > 0

async def list_episodes_for_admin(parent_id: str, parent_type: str, include_deleted: bool = False) -> List[Dict[str, Any]]:
    db = get_db()
    query = {}
    
    if parent_type == "anime":
        query["anime_id"] = parent_id
    elif parent_type == "tv_series":
        query["tv_series_id"] = parent_id
        
    if not include_deleted:
        query["is_deleted"] = {"$ne": True}
        
    cursor = db["episodes"].find(query).sort("episode_number", 1)
    return await cursor.to_list(None)
