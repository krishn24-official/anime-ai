from app.db.mongo import get_db


async def get_all_anime(page: int = 1, limit: int = 50):

    db = get_db()
    skip = (page - 1) * limit

    items = await (
        db["anime"]
        .find(
            {
                "is_deleted": False
            }
        )
        .sort([("title.english", 1)])
        .skip(skip)
        .limit(limit)
        .to_list(None)
    )

    total = await db["anime"].count_documents({"is_deleted": False})

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

async def list_anime_for_admin(include_deleted: bool = False, search: str = None, limit: int = 50, skip: int = 0, needs_review: bool = False):
    db = get_db()
    query = {}
    
    if not include_deleted:
        query["is_deleted"] = {"$ne": True}
        
    if needs_review:
        query["needs_release_review"] = True
        
    if search:
        query["$or"] = [
            {"title.english": {"$regex": search, "$options": "i"}},
            {"title.romaji": {"$regex": search, "$options": "i"}}
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