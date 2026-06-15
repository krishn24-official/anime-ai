from datetime import datetime, timezone

from app.db.mongo import get_db


async def add_to_watchlist(user_id, content_type: str, content_id):
    db = get_db()

    now = datetime.now(timezone.utc)

    await db["watchlist"].update_one(
        {
            "user_id": user_id,
            "content_type": content_type,
            "content_id": content_id,
        },
        {
            "$setOnInsert": {
                "added_at": now,
            },
        },
        upsert=True,
    )


async def remove_from_watchlist(user_id, content_type: str, content_id):
    db = get_db()

    result = await db["watchlist"].delete_one({
        "user_id": user_id,
        "content_type": content_type,
        "content_id": content_id,
    })

    return result.deleted_count > 0


async def is_in_watchlist(user_id, content_type: str, content_id) -> bool:
    db = get_db()

    existing = await db["watchlist"].find_one({
        "user_id": user_id,
        "content_type": content_type,
        "content_id": content_id,
    }, {"_id": 1})

    return existing is not None


async def get_user_watchlist(user_id):
    db = get_db()

    return await (
        db["watchlist"]
        .find({"user_id": user_id})
        .sort("added_at", -1)
        .to_list(None)
    )