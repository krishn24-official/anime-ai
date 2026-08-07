from app.db.mongo import get_db
import re
from app.utils.search_utils import build_fuzzy_search_regex


async def get_all_anime(page: int = 1, limit: int = 50, search: str = None):

    db = get_db()
    skip = (page - 1) * limit
    
    query = {"is_deleted": False}
    if search:
        fuzzy_pattern = build_fuzzy_search_regex(search)
        search_regex = re.compile(fuzzy_pattern, re.IGNORECASE)
        query["$or"] = [
            {"title.english": search_regex},
            {"title.romaji": search_regex}
        ]

    items = await (
        db["anime"]
        .find(query)
        .sort([("title.english", 1)])
        .skip(skip)
        .limit(limit)
        .to_list(None)
    )

    total = await db["anime"].count_documents(query)

    return items, total


async def get_anime_by_id(
    anime_id: str
):

    db = get_db()

    return await (
        db["anime"]
        .find_one(
            {
                "_id": anime_id,
                "is_deleted": False
            }
        )
    )


async def search_anime(
    query: str
):

    db = get_db()

    return await (
        db["anime"]
        .find(
            {
                "$or": [
                    {
                        "title.english": {
                            "$regex": query,
                            "$options": "i"
                        }
                    },
                    {
                        "title.romaji": {
                            "$regex": query,
                            "$options": "i"
                        }
                    }
                ]
            }
        )
        .to_list(None)
    )

async def get_anime_characters(
    anime_id: str
):

    db = get_db()

    return await (
        db["characters"]
        .find(
            {
                "anime_ids": anime_id,
                "is_deleted": False
            },
            {
                "_id": 1,
                "name": 1,
                "images.profile": 1,
                "role": 1
            }
        )
        .to_list(None)
    )

async def get_character_count(
    anime_id: str
):

    db = get_db()

    return await (
        db["characters"]
        .count_documents(
            {
                "anime_ids": anime_id,
                "is_deleted": False
            }
        )
    )

# --- Admin Operations ---

async def find_anime_by_slug(slug: str):
    db = get_db()
    return await db["anime"].find_one({"_id": f"anime_{slug}"})

async def create_anime(doc: dict):
    db = get_db()
    result = await db["anime"].insert_one(doc)
    return str(result.inserted_id)

async def update_anime(content_id: str, updates: dict):
    db = get_db()
    result = await db["anime"].update_one(
        {"_id": content_id},
        {"$set": updates}
    )
    return result.modified_count > 0

async def soft_delete_anime(content_id: str):
    from datetime import datetime, timezone
    db = get_db()
    result = await db["anime"].update_one(
        {"_id": content_id},
        {"$set": {"is_deleted": True, "deleted_at": datetime.now(timezone.utc)}}
    )
    return result.modified_count > 0

async def list_anime_for_admin(include_deleted: bool = False, search: str = None, limit: int = 50, skip: int = 0, needs_review: bool = False, flagged_duplicates_only: bool = False):
    db = get_db()
    query = {}
    
    if not include_deleted:
        query["is_deleted"] = {"$ne": True}
        
    if needs_review:
        query["needs_release_review"] = True
        
    if flagged_duplicates_only:
        query["possible_duplicate_of"] = {"$exists": True, "$ne": None}
        
    if search:
        fuzzy_pattern = build_fuzzy_search_regex(search)
        search_regex = re.compile(fuzzy_pattern, re.IGNORECASE)
        query["$or"] = [
            {"title.english": search_regex},
            {"title.romaji": search_regex}
        ]
        
    cursor = db["anime"].find(query).skip(skip).limit(limit).sort("_id", -1)
    
    total = await db["anime"].count_documents(query)
    items = await cursor.to_list(None)
    
    return {
        "items": items,
        "total": total
    }

async def find_anime_by_ids(anime_ids: list):
    db = get_db()
    return await (
        db["anime"]
        .find(
            {
                "_id": {"$in": anime_ids},
                "is_deleted": False
            }
        )
        .to_list(None)
    )

async def get_anime_voice_actors(anime_id: str, limit: int = 10):
    db = get_db()
    
    characters = await db["characters"].find(
        {"anime_ids": anime_id, "is_deleted": False}
    ).to_list(None)
    
    va_map = {}
    va_ids = []
    
    for char in characters:
        for va_id in char.get("voice_actor_ids", []):
            if va_id not in va_map:
                va_ids.append(va_id)
                va_map[va_id] = {"character_name": char.get("name", "Unknown"), "character_id": char["_id"]}
                
    if not va_ids:
        return []
        
    voice_actors = await db["voice_actors"].find(
        {"_id": {"$in": va_ids[:limit]}, "is_deleted": False}
    ).to_list(None)
    
    result = []
    for va in voice_actors:
        va_id = va["_id"]
        # Convert _id to id
        va["id"] = va_id
        # We need to assign character as role
        va["role"] = f"as {va_map[va_id]['character_name']}"
        result.append(va)
        
    return result