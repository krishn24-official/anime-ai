from app.db.mongo import get_db


async def get_all_characters():

    db = get_db()

    return await (
        db["characters"]
        .find({"is_deleted": False})
        .to_list(None)
    )


async def get_character_by_id(
    character_id: str
):

    db = get_db()

    return await (
        db["characters"]
        .find_one(
            {
                "_id": character_id,
                "is_deleted": False
            }
        )
    )


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
            }
        )
        .to_list(None)
    )

async def get_character_basic(
    character_id: str
):

    db = get_db()

    return await db["characters"].find_one(
        {
            "_id": character_id,
            "is_deleted": False
        },
        {
            "_id": 1,
            "name": 1,
            "images.profile": 1,
            "role": 1
        }
    )