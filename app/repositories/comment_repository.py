from datetime import datetime, timezone

from bson import ObjectId

from app.db.mongo import get_db


async def create_comment(user_id, content_type: str, content_id, text: str, parent_id=None, is_spoiler: bool = False):
    db = get_db()

    doc = {
        "user_id": user_id,
        "content_type": content_type,
        "content_id": content_id,
        "text": text,
        "parent_id": parent_id,
        "is_public": True,     # all comments are public by default
        "is_spoiler": is_spoiler,
        "likes": [],
        "created_at": datetime.now(timezone.utc),
    }

    result = await db["comments"].insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def get_comments_for_content(content_type: str, content_id):
    """Get all public comments for a content item, sorted by likes then chronologically."""
    db = get_db()

    pipeline = [
        {"$match": {
            "content_type": content_type,
            "content_id": content_id,
            "is_public": True,
        }},
        {"$addFields": {
            "like_count": {
                "$cond": {
                    "if": {"$isArray": "$likes"},
                    "then": {"$size": "$likes"},
                    "else": 0
                }
            }
        }},
        {"$sort": {"like_count": -1, "created_at": -1}}
    ]

    cursor = await db["comments"].aggregate(pipeline)
    return await cursor.to_list(length=None)


async def toggle_like_comment(user_id: ObjectId, comment_id: ObjectId):
    """Toggles a like by the user. Returns (new_like_count, is_liked)."""
    db = get_db()
    comment = await db["comments"].find_one({"_id": comment_id})
    if not comment:
        return None

    likes = comment.get("likes", [])
    if not isinstance(likes, list):
        likes = []
    
    # Check if user already liked
    is_liked = False
    for uid in likes:
        if str(uid) == str(user_id):
            is_liked = True
            break
            
    if is_liked:
        # Unlike
        likes = [u for u in likes if str(u) != str(user_id)]
        await db["comments"].update_one(
            {"_id": comment_id},
            {"$set": {"likes": likes}}
        )
        return len(likes), False
    else:
        # Like
        likes.append(user_id)
        await db["comments"].update_one(
            {"_id": comment_id},
            {"$set": {"likes": likes}}
        )
        return len(likes), True


async def get_comment_by_id(comment_id: ObjectId):
    db = get_db()
    return await db["comments"].find_one({"_id": comment_id})


async def delete_comment(comment_id: ObjectId):
    db = get_db()
    result = await db["comments"].delete_one({"_id": comment_id})
    return result.deleted_count > 0