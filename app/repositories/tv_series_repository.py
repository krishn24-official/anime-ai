from app.db.mongo import get_db


async def get_all_tv_series(page: int = 1, limit: int = 20):
    db = get_db()
    skip = (page - 1) * limit

    items = await (
        db["tv_series"]
        .find({"is_deleted": {"$ne": True}})
        .sort([("year", -1), ("title", 1)])
        .skip(skip)
        .limit(limit)
        .to_list(None)
    )

    total = await db["tv_series"].count_documents({"is_deleted": {"$ne": True}})

    return items, total


async def get_tv_series_by_id(series_id: str):
    db = get_db()
    return await db["tv_series"].find_one({"_id": series_id})


async def upsert_tv_series(doc: dict):
    """Insert or update a TV series document by _id."""
    db = get_db()
    await db["tv_series"].replace_one(
        {"_id": doc["_id"]},
        doc,
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
    needs_review: bool = False
):
    db = get_db()
    query = {}
    
    if not include_deleted:
        query["is_deleted"] = {"$ne": True}
        
    if needs_review:
        query["needs_release_review"] = True
        
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"original_title": {"$regex": search, "$options": "i"}}
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