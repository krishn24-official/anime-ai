from datetime import datetime, timezone

from bson import ObjectId

from app.db.mongo import get_db


async def create_comment(user_id, content_type: str, content_id, text: str, parent_id=None):
    db = get_db()

    doc = {
        "user_id": user_id,
        "content_type": content_type,
        "content_id": content_id,
        "text": text,
        "parent_id": parent_id,
        "is_public": True,     # all comments are public by default
        "likes": 0,
        "created_at": datetime.now(timezone.utc),
    }

    result = await db["comments"].insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def get_comments_for_content(content_type: str, content_id):
    """Get all public comments for a content item."""
    db = get_db()

    return await (
        db["comments"]
        .find({
            "content_type": content_type,
            "content_id": content_id,
            "is_public": True,
        })
        .sort("created_at", 1)
        .to_list(None)
    )


async def get_comment_by_id(comment_id: ObjectId):
    db = get_db()
    return await db["comments"].find_one({"_id": comment_id})


async def delete_comment(comment_id: ObjectId):
    db = get_db()
    result = await db["comments"].delete_one({"_id": comment_id})
    return result.deleted_count > 0