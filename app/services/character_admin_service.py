from datetime import datetime, timezone
from app.backend.utils.slug import create_slug
from app.repositories import character_admin_repository
from app.repositories.anime_repository import get_anime_by_id
from app.repositories.manga_repository import get_manga_by_id
from app.services.cloudinary_service import upload_image_from_bytes
from app.db.mongo import get_db

async def _validate_relations(anime_ids: list[str], manga_ids: list[str]):
    db = get_db()
    
    valid_anime = []
    for aid in anime_ids:
        # Anime field can contain anime, movies, or tv_series
        if await get_anime_by_id(aid):
            valid_anime.append(aid)
        elif await db["movies"].find_one({"_id": aid, "is_deleted": False}):
            valid_anime.append(aid)
        elif await db["tv_series"].find_one({"_id": aid, "is_deleted": False}):
            valid_anime.append(aid)
            
    valid_manga = []
    for mid in manga_ids:
        if await get_manga_by_id(mid):
            valid_manga.append(mid)
            
    return valid_anime, valid_manga


async def create_character(
    admin_id: str,
    name: str,
    native_name: str | None,
    birth_day: int | None,
    birth_month: int | None,
    height: str | None,
    hair_color: str | None,
    has_hair: bool | None,
    description: str | None,
    anime_ids: list[str],
    manga_ids: list[str],
    affiliations: list[str],
    abilities: list[str],
    forms: list[str],
    status: str,
    species: str,
    gender: str | None,
    role: str,
    tags: list[str],
    profile_bytes: bytes | None,
    banner_bytes: bytes | None
):
    name = name.strip()
    if not name:
        raise ValueError("Name is required")
        
    slug = create_slug(name)
    content_id = f"char_{slug}"
    
    existing = await character_admin_repository.find_character_by_slug(slug)
    if existing:
        raise ValueError(f"A character with this name already exists (content_id: {content_id}). Edit the existing entry instead, or use a more specific name.")
        
    if birth_day is not None and (birth_day < 1 or birth_day > 31):
        raise ValueError("Birth day must be between 1 and 31")
    if birth_month is not None and (birth_month < 1 or birth_month > 12):
        raise ValueError("Birth month must be between 1 and 12")
        
    valid_anime, valid_manga = await _validate_relations(anime_ids, manga_ids)
    
    images = {"profile": None, "banner": None}
    
    if profile_bytes:
        profile_url = upload_image_from_bytes(
            profile_bytes, 
            folder="characters", 
            public_id=f"{content_id}_profile"
        )
        images["profile"] = profile_url
        
    if banner_bytes:
        banner_url = upload_image_from_bytes(
            banner_bytes, 
            folder="characters", 
            public_id=f"{content_id}_banner"
        )
        images["banner"] = banner_url
        
    doc = {
        "_id": content_id,
        "name": name,
        "native_name": native_name.strip() if native_name else None,
        "birth_day": birth_day,
        "birth_month": birth_month,
        "physical": {
            "height": height.strip() if height else None,
            "hair_color": hair_color.strip() if hair_color else None,
            "has_hair": has_hair
        },
        "description": description.strip() if description else None,
        "images": images,
        "anime_ids": valid_anime,
        "manga_ids": valid_manga,
        "voice_actor_ids": [],
        "affiliations": [a.strip() for a in affiliations if a.strip()],
        "abilities": [a.strip() for a in abilities if a.strip()],
        "forms": [f.strip() for f in forms if f.strip()],
        "status": status.strip() if status else "unknown",
        "species": species.strip() if species else "unknown",
        "gender": gender.strip() if gender else None,
        "role": role.strip() if role else "unknown",
        "tags": [t.strip() for t in tags if t.strip()],
        "source_metadata": {
            "source": "manual",
            "created_by": admin_id
        },
        "is_deleted": False,
        "deleted_at": None
    }
    
    await character_admin_repository.create_character(doc)
    return content_id

async def update_character(
    admin_id: str,
    content_id: str,
    name: str | None,
    native_name: str | None,
    birth_day: int | None,
    birth_month: int | None,
    height: str | None,
    hair_color: str | None,
    has_hair: bool | None,
    description: str | None,
    anime_ids: list[str] | None,
    manga_ids: list[str] | None,
    affiliations: list[str] | None,
    abilities: list[str] | None,
    forms: list[str] | None,
    status: str | None,
    species: str | None,
    gender: str | None,
    role: str | None,
    tags: list[str] | None,
    profile_bytes: bytes | None,
    banner_bytes: bytes | None
):
    slug = content_id.replace("char_", "", 1)
    existing = await character_admin_repository.find_character_by_slug(slug)
    if not existing:
        raise ValueError(f"Character {content_id} not found")
        
    updates = {}
    
    if name is not None:
        updates["name"] = name.strip()
    if native_name is not None:
        updates["native_name"] = native_name.strip() if native_name else None
    
    if birth_day is not None or birth_month is not None:
        bday = birth_day if birth_day is not None else existing.get("birth_day")
        bmonth = birth_month if birth_month is not None else existing.get("birth_month")
        if bday is not None and (bday < 1 or bday > 31):
            raise ValueError("Birth day must be between 1 and 31")
        if bmonth is not None and (bmonth < 1 or bmonth > 12):
            raise ValueError("Birth month must be between 1 and 12")
        if birth_day is not None: updates["birth_day"] = birth_day
        if birth_month is not None: updates["birth_month"] = birth_month
        
    if anime_ids is not None or manga_ids is not None:
        a_ids = anime_ids if anime_ids is not None else existing.get("anime_ids", [])
        m_ids = manga_ids if manga_ids is not None else existing.get("manga_ids", [])
        valid_anime, valid_manga = await _validate_relations(a_ids, m_ids)
        if anime_ids is not None: updates["anime_ids"] = valid_anime
        if manga_ids is not None: updates["manga_ids"] = valid_manga
        
    if profile_bytes:
        profile_url = upload_image_from_bytes(
            profile_bytes, 
            folder="characters", 
            public_id=f"{content_id}_profile"
        )
        updates["images.profile"] = profile_url
        
    if banner_bytes:
        banner_url = upload_image_from_bytes(
            banner_bytes, 
            folder="characters", 
            public_id=f"{content_id}_banner"
        )
        updates["images.banner"] = banner_url
        
    if height is not None: updates["physical.height"] = height.strip() if height else None
    if hair_color is not None: updates["physical.hair_color"] = hair_color.strip() if hair_color else None
    if has_hair is not None: updates["physical.has_hair"] = has_hair
    
    if description is not None: updates["description"] = description.strip() if description else None
    
    if affiliations is not None: updates["affiliations"] = [a.strip() for a in affiliations if a.strip()]
    if abilities is not None: updates["abilities"] = [a.strip() for a in abilities if a.strip()]
    if forms is not None: updates["forms"] = [f.strip() for f in forms if f.strip()]
    
    if status is not None: updates["status"] = status.strip() if status else "unknown"
    if species is not None: updates["species"] = species.strip() if species else "unknown"
    if gender is not None: updates["gender"] = gender.strip() if gender else None
    if role is not None: updates["role"] = role.strip() if role else "unknown"
    if tags is not None: updates["tags"] = [t.strip() for t in tags if t.strip()]
    
    if updates:
        await character_admin_repository.update_character(content_id, updates)
        
    return content_id

async def delete_character(content_id: str):
    slug = content_id.replace("char_", "", 1)
    existing = await character_admin_repository.find_character_by_slug(slug)
    if not existing:
        raise ValueError(f"Character {content_id} not found")
        
    await character_admin_repository.soft_delete_character(content_id)
    return True
