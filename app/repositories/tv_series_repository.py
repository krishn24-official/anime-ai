from app.db.mongo import get_db
import re
from app.utils.search_utils import build_fuzzy_search_regex


async def get_all_tv_series(page: int = 1, limit: int = 20, search: str = None):
    db = get_db()
    skip = (page - 1) * limit

    query = {"is_deleted": {"$ne": True}}
    if search:
        fuzzy_pattern = build_fuzzy_search_regex(search)
        search_regex = re.compile(fuzzy_pattern, re.IGNORECASE)
        query["title"] = search_regex

    items = await (
        db["tv_series"]
        .find(query)
        .sort([("year", -1), ("title", 1)])
        .skip(skip)
        .limit(limit)
        .to_list(None)
    )

    total = await db["tv_series"].count_documents(query)

    return items, total


async def get_tv_series_by_id(series_id: str):
    db = get_db()
    return await db["tv_series"].find_one({"_id": series_id})


async def upsert_tv_series(doc: dict):
    """Insert or update a TV series document by _id."""
    db = get_db()
    
    # Check for cross-collection duplicates before insert
    from app.services.duplicate_detection_service import check_for_duplicate, apply_reciprocal_duplicate_flag
    dup = await check_for_duplicate(doc, "tv_series")
    if dup:
        doc["possible_duplicate_of"] = dup
        await apply_reciprocal_duplicate_flag(doc["_id"], "tv_series", dup)
        print(f"⚠️ Possible duplicate detected: '{doc.get('title')}' ({doc['_id']}) may duplicate {dup['content_type']}_{dup['content_id']} -- flagged, not skipped")
        
    await db["tv_series"].update_one(
        {"_id": doc["_id"]},
        {"$setOnInsert": doc},
        upsert=True,
    )
    return doc

# --- Admin Operations ---

async def find_tv_series_by_slug(slug: str):
    db = get_db()
    return await db["tv_series"].find_one({"_id": f"tv_{slug}"})

async def create_tv_series(doc: dict):
    db = get_db()
    result = await db["tv_series"].insert_one(doc)
    return str(result.inserted_id)

async def update_tv_series(content_id: str, updates: dict):
    db = get_db()
    result = await db["tv_series"].update_one(
        {"_id": content_id},
        {"$set": updates}
    )
    return result.modified_count > 0

async def soft_delete_tv_series(content_id: str):
    from datetime import datetime, timezone
    db = get_db()
    result = await db["tv_series"].update_one(
        {"_id": content_id},
        {"$set": {"is_deleted": True, "deleted_at": datetime.now(timezone.utc)}}
    )
    return result.modified_count > 0

async def list_tv_series_for_admin(
    include_deleted: bool = False,
    search: str | None = None,
    limit: int = 50,
    skip: int = 0,
    needs_review: bool = False,
    flagged_duplicates_only: bool = False
):
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
        
    cursor = db["tv_series"].find(query).skip(skip).limit(limit).sort("_id", -1)
    
    items = await cursor.to_list(None)
    total = await db["tv_series"].count_documents(query)
    
    return {
        "items": items,
        "total": total,
        "page": (skip // limit) + 1,
        "pages": (total + limit - 1) // limit
    }