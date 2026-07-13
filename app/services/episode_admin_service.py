import re
from typing import Optional
from datetime import datetime
from app.repositories import episode_repository
from app.repositories.anime_repository import get_anime_by_id
from app.repositories.tv_series_repository import get_tv_series_by_id
from bson import ObjectId

def to_object_id(id_str: str) -> Optional[ObjectId]:
    try:
        return ObjectId(id_str)
    except Exception:
        return None

async def create_episode(
    admin_id: str,
    parent_type: str,
    parent_content_id: str,
    episode_number: int,
    title: Optional[str] = None,
    release_date: Optional[str] = None,
    director: Optional[str] = None,
    arc: Optional[str] = None,
    is_filler: bool = False,
    canon_type: Optional[str] = None,
    summary: Optional[str] = None
) -> dict:
    if parent_type not in ["anime", "tv_series"]:
        raise ValueError("parent_type must be either 'anime' or 'tv_series'")
        
    # Validate parent existence
    if parent_type == "anime":
        parent = await get_anime_by_id(parent_content_id)
    else:
        parent = await get_tv_series_by_id(parent_content_id)
        
    if not parent or parent.get("is_deleted"):
        raise ValueError(f"Parent {parent_type} not found")
        
    # Validate release date format
    if release_date:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", release_date):
            raise ValueError("release_date must be in YYYY-MM-DD format")
            
    # Check duplicates
    anime_id = parent_content_id if parent_type == "anime" else None
    tv_series_id = parent_content_id if parent_type == "tv_series" else None
    
    existing = await episode_repository.find_episode(anime_id, tv_series_id, episode_number)
    if existing:
        raise ValueError("An episode with this number already exists for this parent")
        
    content_id = f"ep_{parent_content_id}_{episode_number}"
    
    doc = {
        "_id": content_id,
        "anime_id": anime_id,
        "tv_series_id": tv_series_id,
        "episode_number": episode_number,
        "title": title,
        "release_date": release_date,
        "director": director,
        "arc": arc,
        "is_filler": is_filler,
        "canon_type": canon_type,
        "summary": summary,
        "manga_chapters": [],
        "is_deleted": False,
        "deleted_at": None,
        "created_by": admin_id,
        "created_at": datetime.utcnow()
    }
    
    return await episode_repository.create_episode(doc)

async def update_episode(
    content_id: str,
    title: Optional[str] = None,
    release_date: Optional[str] = None,
    director: Optional[str] = None,
    arc: Optional[str] = None,
    is_filler: Optional[bool] = None,
    canon_type: Optional[str] = None,
    summary: Optional[str] = None
) -> bool:
    if release_date:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", release_date):
            raise ValueError("release_date must be in YYYY-MM-DD format")
            
    updates = {}
    if title is not None: updates["title"] = title
    if release_date is not None: updates["release_date"] = release_date
    if director is not None: updates["director"] = director
    if arc is not None: updates["arc"] = arc
    if is_filler is not None: updates["is_filler"] = is_filler
    if canon_type is not None: updates["canon_type"] = canon_type
    if summary is not None: updates["summary"] = summary
    
    if updates:
        updates["updated_at"] = datetime.utcnow()
        
    return await episode_repository.update_episode(content_id, updates)

async def delete_episode(content_id: str) -> bool:
    return await episode_repository.soft_delete_episode(content_id)
