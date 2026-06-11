from app.db.mongo import get_db


async def search_characters(
    query: str
):

    db = get_db()

    return await (
        db["characters"]
        .find(
            {
                "name": {
                    "$regex": query,
                    "$options": "i"
                },
                "is_deleted": False
            },
            {
                "_id": 1,
                "name": 1,
                "images.profile": 1,
                "role": 1
            }
        )
        .limit(10)
        .to_list(None)
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
                ],
                "is_deleted": False
            },
            {
                "_id": 1,
                "title": 1,
                "images": 1,
                "year": 1
            }
        )
        .limit(10)
        .to_list(None)
    )


async def search_manga(
    query: str
):

    db = get_db()

    return await (
        db["manga"]
        .find(
            {
                "name": {
                    "$regex": query,
                    "$options": "i"
                },
                "is_deleted": False
            },
            {
                "_id": 1,
                "name": 1,
                "cover_image": 1,
                "status": 1
            }
        )
        .limit(10)
        .to_list(None)
    )