from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId

from app.db.mongo import get_db


async def get_user_by_email(email: str):
    db = get_db()
    return await db["users"].find_one({"email": email.lower()})


async def get_user_by_id(user_id: str):
    db = get_db()
    try:
        oid = ObjectId(user_id)
    except InvalidId:
        return None
    return await db["users"].find_one({"_id": oid})


async def create_user(email: str, hashed_password: str, display_name: str = ""):
    db = get_db()

    doc = {
        "email": email.lower(),
        "password_hash": hashed_password,
        "display_name": display_name or email.split("@")[0],
        "created_at": datetime.now(timezone.utc),
    }

    result = await db["users"].insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc