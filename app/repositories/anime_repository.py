from app.db.mongo import get_db


async def get_all_anime():

    db = get_db()

    return await (
        db["anime"]
        .find(
            {
                "is_deleted": False
            }
        )
        .to_list(None)
    )


async def get_anime_by_id(
    anime_id: str
):

    db = get_db()

    return await (
        db["anime"]
        .find_one(
            {
                "_id": anime_id,
                "is_deleted": False
            }
        )
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
                ]
            }
        )
        .to_list(None)
    )

async def get_anime_characters(
    anime_id: str
):

    db = get_db()

    return await (
        db["characters"]
        .find(
            {
                "anime_ids": anime_id,
                "is_deleted": False
            },
            {
                "_id": 1,
                "name": 1,
                "images.profile": 1,
                "role": 1
            }
        )
        .to_list(None)
    )

async def get_character_count(
    anime_id: str
):

    db = get_db()

    return await (
        db["characters"]
        .count_documents(
            {
                "anime_ids": anime_id,
                "is_deleted": False
            }
        )
    )