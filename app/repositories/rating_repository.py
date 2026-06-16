from datetime import datetime, timezone

from app.db.mongo import get_db
from app.services.rating_scale import rating_to_weight, weight_to_label


async def upsert_rating(user_id, content_type: str, content_id, rating: str):
    db = get_db()

    now = datetime.now(timezone.utc)
    weight = rating_to_weight(rating)

    await db["ratings"].update_one(
        {
            "user_id": user_id,
            "content_type": content_type,
            "content_id": content_id,
        },
        {
            "$set": {
                "rating": rating,
                "rating_weight": weight,
                "updated_at": now,
            },
            "$setOnInsert": {
                "created_at": now,
            },
        },
        upsert=True,
    )


async def get_user_rating(user_id, content_type: str, content_id):
    db = get_db()
    return await db["ratings"].find_one({
        "user_id": user_id,
        "content_type": content_type,
        "content_id": content_id,
    })


async def get_rating_stats(content_type: str, content_id):
    db = get_db()

    pipeline = [
        {"$match": {"content_type": content_type, "content_id": content_id}},
        {"$group": {
            "_id": None,
            "average_weight": {"$avg": "$rating_weight"},
            "count": {"$sum": 1},
        }},
    ]

    result = await db["ratings"].aggregate(pipeline).to_list(None)

    if not result:
        return {"average_rating": None, "average_weight": 0, "count": 0}

    average_weight = round(result[0]["average_weight"], 2)

    return {
        "average_rating": weight_to_label(average_weight),
        "average_weight": average_weight,
        "count": result[0]["count"],
    }


async def delete_rating(user_id, content_type: str, content_id):
    db = get_db()
    await db["ratings"].delete_one({
        "user_id": user_id,
        "content_type": content_type,
        "content_id": content_id,
    })


async def get_top_rated(content_type: str | None = None, limit: int = 10):
    """Aggregate top-rated content by average weight, optionally filtered by type."""
    db = get_db()

    match = {}
    if content_type:
        match["content_type"] = content_type

    pipeline = [
        *([ {"$match": match} ] if match else []),
        {"$group": {
            "_id": {
                "content_type": "$content_type",
                "content_id": "$content_id",
            },
            "average_weight": {"$avg": "$rating_weight"},
            "count": {"$sum": 1},
            # most common rating label for display
            "top_rating": {"$max": "$rating"},
        }},
        {"$sort": {"average_weight": -1, "count": -1}},
        {"$limit": limit},
    ]

    results = await db["ratings"].aggregate(pipeline).to_list(None)
    return results


async def get_watchlist_counts(content_type: str | None = None, limit: int = 10):
    """Aggregate most-watchlisted content."""
    db = get_db()

    match = {}
    if content_type:
        match["content_type"] = content_type

    pipeline = [
        *([ {"$match": match} ] if match else []),
        {"$group": {
            "_id": {
                "content_type": "$content_type",
                "content_id": "$content_id",
            },
            "count": {"$sum": 1},
        }},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]

    results = await db["watchlist"].aggregate(pipeline).to_list(None)
    return results