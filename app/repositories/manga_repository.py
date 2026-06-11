from app.db.mongo import get_db


async def get_all_manga():

    db = get_db()

    return await (
        db["manga"]
        .find(
            {
                "is_deleted": False
            }
        )
        .to_list(None)
    )


async def get_manga_by_id(
    manga_id: str
):

    db = get_db()

    return await (
        db["manga"]
        .find_one(
            {
                "_id": manga_id,
                "is_deleted": False
            }
        )
    )


async def search_manga(
    query: str
):

    db = get_db()

    return await (
        db["manga"]
        .find(
            {
                "$or": [
                    {
                        "name": {
                            "$regex": query,
                            "$options": "i"
                        }
                    },
                    {
                        "native_name": {
                            "$regex": query,
                            "$options": "i"
                        }
                    }
                ]
            }
        )
        .to_list(None)
    )