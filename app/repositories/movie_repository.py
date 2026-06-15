from app.db.mongo import get_db


async def get_all_movies(page: int = 1, limit: int = 20):
    db = get_db()
    skip = (page - 1) * limit

    items = await (
        db["movies"]
        .find({"is_deleted": {"$ne": True}})
        .sort("title", 1)
        .skip(skip)
        .limit(limit)
        .to_list(None)
    )

    total = await db["movies"].count_documents({"is_deleted": {"$ne": True}})

    return items, total


async def get_movie_by_id(movie_id: str):
    db = get_db()
    return await db["movies"].find_one({"_id": movie_id})