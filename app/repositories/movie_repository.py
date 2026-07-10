from app.db.mongo import get_db


async def get_all_movies(page: int = 1, limit: int = 20):
    db = get_db()
    skip = (page - 1) * limit

    items = await (
        db["movies"]
        .find({"is_deleted": {"$ne": True}})
        .sort([("year", -1), ("title", 1)])
        .skip(skip)
        .limit(limit)
        .to_list(None)
    )

    total = await db["movies"].count_documents({"is_deleted": {"$ne": True}})

    return items, total


async def get_movie_by_id(movie_id: str):
    db = get_db()
    return await db["movies"].find_one({"_id": movie_id})


async def upsert_movie(doc: dict):
    """Insert or update a movie document by _id."""
    db = get_db()
    await db["movies"].replace_one(
        {"_id": doc["_id"]},
        doc,
        upsert=True,
    )
    return doc