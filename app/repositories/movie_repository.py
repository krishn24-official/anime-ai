from app.db.mongo import get_db
import re
from app.utils.search_utils import build_fuzzy_search_regex


async def get_all_movies(page: int = 1, limit: int = 20, search: str = None):
    db = get_db()
    skip = (page - 1) * limit
    
    query = {"is_deleted": {"$ne": True}}
    if search:
        fuzzy_pattern = build_fuzzy_search_regex(search)
        search_regex = re.compile(fuzzy_pattern, re.IGNORECASE)
        query["title"] = search_regex

    items = await (
        db["movies"]
        .find(query)
        .sort([("year", -1), ("title", 1)])
        .skip(skip)
        .limit(limit)
        .to_list(None)
    )

    total = await db["movies"].count_documents(query)

    return items, total


async def get_movie_by_id(movie_id: str):
    db = get_db()
    return await db["movies"].find_one({"_id": movie_id})


async def upsert_movie(doc: dict):
    """Insert or update a movie document by _id."""
    db = get_db()
    
    # Check for cross-collection duplicates before insert
    from app.services.duplicate_detection_service import check_for_duplicate, apply_reciprocal_duplicate_flag
    dup = await check_for_duplicate(doc, "movie")
    if dup:
        doc["possible_duplicate_of"] = dup
        await apply_reciprocal_duplicate_flag(doc["_id"], "movie", dup)
        print(f"⚠️ Possible duplicate detected: '{doc.get('title')}' ({doc['_id']}) may duplicate {dup['content_type']}_{dup['content_id']} -- flagged, not skipped")
        
    await db["movies"].update_one(
        {"_id": doc["_id"]},
        {"$setOnInsert": doc},
        upsert=True,
    )
    return doc

# --- Admin Operations ---

async def find_movie_by_slug(slug: str):
    db = get_db()
    return await db["movies"].find_one({"_id": f"movie_{slug}"})

async def create_movie(doc: dict):
    db = get_db()
    result = await db["movies"].insert_one(doc)
    return str(result.inserted_id)

async def update_movie(content_id: str, updates: dict):
    db = get_db()
    result = await db["movies"].update_one(
        {"_id": content_id},
        {"$set": updates}
    )
    return result.modified_count > 0

async def soft_delete_movie(content_id: str):
    from datetime import datetime, timezone
    db = get_db()
    result = await db["movies"].update_one(
        {"_id": content_id},
        {"$set": {"is_deleted": True, "deleted_at": datetime.now(timezone.utc)}}
    )
    return result.modified_count > 0

async def list_movies_for_admin(include_deleted: bool = False, search: str = None, limit: int = 50, skip: int = 0, needs_review: bool = False, flagged_duplicates_only: bool = False):
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
            {"title": search_regex},
            {"original_title": search_regex}
        ]
        
    cursor = db["movies"].find(query).skip(skip).limit(limit).sort("_id", -1)
    
    total = await db["movies"].count_documents(query)
    items = await cursor.to_list(None)
    
    return {
        "items": items,
        "total": total
    }