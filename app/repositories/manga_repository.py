from app.db.mongo import get_db


async def get_all_manga(page: int = 1, limit: int = 50):

    db = get_db()
    skip = (page - 1) * limit

    query = {"is_deleted": False}

    items = await (
        db["manga"]
        .find(query)
        .sort([("name", 1)])
        .skip(skip)
        .limit(limit)
        .to_list(None)
    )

    total = await db["manga"].count_documents(query)

    return items, total


async def get_manga_by_id(manga_id: str):

    db = get_db()

    return await db["manga"].find_one({"_id": manga_id, "is_deleted": False})


