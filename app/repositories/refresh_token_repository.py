from datetime import datetime, timezone

from bson import ObjectId

from app.db.mongo import get_db


async def save_refresh_token(user_id: ObjectId, token: str, expires_at: datetime):
    db = get_db()
    await db["refresh_tokens"].insert_one({
        "user_id": user_id,
        "token": token,
        "expires_at": expires_at,
        "created_at": datetime.now(timezone.utc),
        "is_revoked": False,
    })


async def get_refresh_token(token: str):
    db = get_db()
    return await db["refresh_tokens"].find_one({
        "token": token,
        "is_revoked": False,
    })


async def revoke_refresh_token(token: str):
    db = get_db()
    await db["refresh_tokens"].update_one(
        {"token": token},
        {"$set": {"is_revoked": True}}
    )


async def revoke_all_user_tokens(user_id: ObjectId):
    """Revoke all refresh tokens for a user — use for 'logout all devices'."""
    db = get_db()
    await db["refresh_tokens"].update_many(
        {"user_id": user_id, "is_revoked": False},
        {"$set": {"is_revoked": True}}
    )


async def delete_expired_tokens():
    """Cleanup job — remove expired tokens. Call periodically."""
    db = get_db()
    now = datetime.now(timezone.utc)
    result = await db["refresh_tokens"].delete_many({"expires_at": {"$lt": now}})
    return result.deleted_count