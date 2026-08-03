from app.db.mongo import get_db


async def search_characters(
    query: str
):

    db = get_db()

    cursor = await db["characters"].aggregate([
        {
            "$match": {
                "name": {
                    "$regex": query,
                    "$options": "i"
                },
                "is_deleted": False
            }
        },
        {
            "$addFields": {
                "name_length": {"$strLenCP": {"$ifNull": ["$name", ""]}}
            }
        },
        {
            "$sort": {"name_length": 1}
        },
        {
            "$limit": 10
        },
        {
            "$project": {
                "_id": 1,
                "name": 1,
                "images.profile": 1,
                "role": 1
            }
        }
    ])
    return await cursor.to_list(None)


async def search_anime(
    query: str
):

    db = get_db()

    cursor = await db["anime"].aggregate([
        {
            "$match": {
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
            }
        },
        {
            "$addFields": {
                "title_length": {"$strLenCP": {"$ifNull": ["$title.english", {"$ifNull": ["$title.romaji", ""]}]}}
            }
        },
        {
            "$sort": {"title_length": 1}
        },
        {
            "$limit": 10
        },
        {
            "$project": {
                "_id": 1,
                "title": 1,
                "images": 1,
                "year": 1
            }
        }
    ])
    return await cursor.to_list(None)


async def search_manga(
    query: str
):

    db = get_db()

    cursor = await db["manga"].aggregate([
        {
            "$match": {
                "name": {
                    "$regex": query,
                    "$options": "i"
                },
                "is_deleted": False
            }
        },
        {
            "$addFields": {
                "name_length": {"$strLenCP": {"$ifNull": ["$name", ""]}}
            }
        },
        {
            "$sort": {"name_length": 1}
        },
        {
            "$limit": 10
        },
        {
            "$project": {
                "_id": 1,
                "name": 1,
                "cover_image": 1,
                "status": 1
            }
        }
    ])
    return await cursor.to_list(None)


async def search_movies(
    query: str
):

    db = get_db()

    cursor = await db["movies"].aggregate([
        {
            "$match": {
                "title": {
                    "$regex": query,
                    "$options": "i"
                },
                "is_deleted": {"$ne": True}
            }
        },
        {
            "$addFields": {
                "title_length": {"$strLenCP": {"$ifNull": ["$title", ""]}}
            }
        },
        {
            "$sort": {"title_length": 1}
        },
        {
            "$limit": 10
        },
        {
            "$project": {
                "_id": 1,
                "title": 1,
                "year": 1,
                "images": 1,
                "genres": 1,
            }
        }
    ])
    return await cursor.to_list(None)


async def search_tv_series(
    query: str
):

    db = get_db()

    cursor = await db["tv_series"].aggregate([
        {
            "$match": {
                "title": {
                    "$regex": query,
                    "$options": "i"
                },
                "is_deleted": {"$ne": True}
            }
        },
        {
            "$addFields": {
                "title_length": {"$strLenCP": {"$ifNull": ["$title", ""]}}
            }
        },
        {
            "$sort": {"title_length": 1}
        },
        {
            "$limit": 10
        },
        {
            "$project": {
                "_id": 1,
                "title": 1,
                "year": 1,
                "images": 1,
                "genres": 1,
                "total_seasons": 1,
            }
        }
    ])
    return await cursor.to_list(None)


async def search_organizations(
    query: str
):
    db = get_db()
    cursor = await db["organizations"].aggregate([
        {
            "$match": {
                "name": {
                    "$regex": query,
                    "$options": "i"
                },
                "is_deleted": {"$ne": True}
            }
        },
        {
            "$addFields": {
                "name_length": {"$strLenCP": {"$ifNull": ["$name", ""]}}
            }
        },
        {
            "$sort": {"name_length": 1}
        },
        {
            "$limit": 10
        },
        {
            "$project": {
                "_id": 1,
                "name": 1,
                "type": 1,
                "images": 1,
                "anime_ids": 1,
                "manga_id": 1
            }
        }
    ])
    results = await cursor.to_list(None)
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