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


async def search_movies(
    query: str
):

    db = get_db()

    return await (
        db["movies"]
        .find(
            {
                "title": {
                    "$regex": query,
                    "$options": "i"
                },
                "is_deleted": {"$ne": True}
            },
            {
                "_id": 1,
                "title": 1,
                "year": 1,
                "images": 1,
                "genres": 1,
            }
        )
        .limit(10)
        .to_list(None)
    )


async def search_tv_series(
    query: str
):

    db = get_db()

    return await (
        db["tv_series"]
        .find(
            {
                "title": {
                    "$regex": query,
                    "$options": "i"
                },
                "is_deleted": {"$ne": True}
            },
            {
                "_id": 1,
                "title": 1,
                "year": 1,
                "images": 1,
                "genres": 1,
                "total_seasons": 1,
            }
        )
        .limit(10)
        .to_list(None)
    )


async def search_organizations(
    query: str
):
    db = get_db()
    results = await (
        db["organizations"]
        .find(
            {
                "name": {
                    "$regex": query,
                    "$options": "i"
                },
                "is_deleted": {"$ne": True}
            },
            {
                "_id": 1,
                "name": 1,
                "type": 1,
                "images": 1,
                "anime_ids": 1,
                "manga_id": 1
            }
        )
        .limit(10)
        .to_list(None)
    )
    # Map _id to id in repo or service. Let's return mapped dictionaries
    return [
        {
            "id": str(org["_id"]),
            "name": org.get("name"),
            "type": org.get("type"),
            "images": org.get("images", {"logo": "", "banner": ""}),
            "anime_ids": org.get("anime_ids", []),
            "manga_id": org.get("manga_id")
        }
        for org in results
    ]