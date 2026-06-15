from app.db.mongo import get_db


async def get_all_tv_series(page: int = 1, limit: int = 20):
    db = get_db()
    skip = (page - 1) * limit

    items = await (
        db["tv_series"]
        .find({"is_deleted": {"$ne": True}})
        .sort("title", 1)
        .skip(skip)
        .limit(limit)
        .to_list(None)
    )

    total = await db["tv_series"].count_documents({"is_deleted": {"$ne": True}})

    return items, total


async def get_tv_series_by_id(series_id: str):
    db = get_db()
    return await db["tv_series"].find_one({"_id": series_id})