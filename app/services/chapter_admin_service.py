import re
from typing import Optional
from datetime import datetime
from app.repositories import chapter_repository
from app.repositories.manga_repository import get_manga_by_id
from bson import ObjectId

def to_object_id(id_str: str) -> Optional[ObjectId]:
    try:
        return ObjectId(id_str)
    except Exception:
        return None

async def create_chapter(
    admin_id: str,
    manga_id: str,
    chapter_number: int,
    release_date: Optional[str] = None,
    summary: Optional[str] = None
) -> dict:
    manga = await get_manga_by_id(manga_id)
    if not manga or manga.get("is_deleted"):
        raise ValueError("Manga not found")
        
    if release_date:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", release_date):
            raise ValueError("release_date must be in YYYY-MM-DD format")
            
    existing = await chapter_repository.find_chapter(manga_id, chapter_number)
    if existing:
        raise ValueError("A chapter with this number already exists for this manga")
        
    content_id = f"ch_{manga_id}_{chapter_number}"
    
    doc = {
        "_id": content_id,
        "manga_id": manga_id,
        "chapter_number": chapter_number,
        "release_date": release_date,
        "summary": summary,
        "is_deleted": False,
        "deleted_at": None,
        "created_by": admin_id,
        "created_at": datetime.utcnow()
    }
    
    return await chapter_repository.create_chapter(doc)

async def update_chapter(
    content_id: str,
    release_date: Optional[str] = None,
    summary: Optional[str] = None
) -> bool:
    if release_date:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", release_date):
            raise ValueError("release_date must be in YYYY-MM-DD format")
            
    updates = {}
    if release_date is not None: updates["release_date"] = release_date
    if summary is not None: updates["summary"] = summary
    
    if updates:
        updates["updated_at"] = datetime.utcnow()
        
    return await chapter_repository.update_chapter(content_id, updates)

async def delete_chapter(content_id: str) -> bool:
    return await chapter_repository.soft_delete_chapter(content_id)
