from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId

from app.db.mongo import get_db


async def get_user_by_email(email: str):
    db = get_db()
    return await db["users"].find_one({"email": email.lower()})


async def get_user_by_username(username: str):
    db = get_db()
    return await db["users"].find_one({"username": username.lower()})


async def get_user_by_email_or_username(identifier: str):
    """Login by email or username."""
    db = get_db()
    identifier = identifier.lower()
    return await db["users"].find_one({
        "$or": [
            {"email": identifier},
            {"username": identifier},
        ]
    })


async def get_user_by_id(user_id: str):
    db = get_db()
    try:
        oid = ObjectId(user_id)
    except InvalidId:
        return None
    return await db["users"].find_one({"_id": oid})


async def create_user(email: str, hashed_password: str, username: str):
    db = get_db()

    doc = {
        "email": email.lower(),
        "username": username.lower(),
        "password_hash": hashed_password,
        "display_name": username,   # defaults to username
        "created_at": datetime.now(timezone.utc),
        "is_active": True,
        "is_admin": False,
    }

    result = await db["users"].insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def set_otp(email: str, otp_hash: str, expires_at: datetime):
    db = get_db()
    await db["users"].update_one(
        {"email": email.lower()},
        {"$set": {
            "otp_hash": otp_hash,
            "otp_expires_at": expires_at,
        }}
    )


async def clear_otp(email: str):
    db = get_db()
    await db["users"].update_one(
        {"email": email.lower()},
        {"$unset": {"otp_hash": "", "otp_expires_at": ""}}
    )


async def update_password(email: str, hashed_password: str):
    db = get_db()
    await db["users"].update_one(
        {"email": email.lower()},
        {"$set": {"password_hash": hashed_password}}
    )