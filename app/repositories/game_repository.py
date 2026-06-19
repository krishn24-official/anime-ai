from app.db.mongo import get_db


async def get_playable_characters():
    """
    Returns characters that have game_properties populated.
    Only includes fields needed for the game — not full character docs.
    """
    db = get_db()

    return await (
        db["characters"]
        .find(
            {
                "game_properties": {"$exists": True, "$ne": []},
                "is_deleted": {"$ne": True},
            },
            {
                "_id": 1,
                "name": 1,
                "images": 1,
                "game_properties": 1,
                "anime_ids": 1,
                "gender": 1,
            }
        )
        .to_list(None)
    )


async def get_characters_without_properties(limit: int = 50):
    """Returns characters that need game property extraction."""
    db = get_db()

    return await (
        db["characters"]
        .find(
            {
                "$or": [
                    {"game_properties": {"$exists": False}},
                    {"game_properties": []},
                ],
                "description": {"$exists": True, "$ne": None, "$ne": ""},
                "is_deleted": {"$ne": True},
            },
            {"_id": 1, "name": 1, "description": 1, "gender": 1, "anime_ids": 1}
        )
        .limit(limit)
        .to_list(None)
    )