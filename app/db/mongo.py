from motor.motor_asyncio import AsyncIOMotorClient
from app.config import MONGO_URI

client = None


async def connect_db():
    global client

    if not MONGO_URI:
        raise RuntimeError("MONGO_URI is not set")

    client = AsyncIOMotorClient(MONGO_URI)

    db = client["anime_ai"]

    # INDEXES
    await db["anime"].create_index("title.english")
    await db["anime"].create_index("title.romaji")
    await db["anime"].create_index("genres")
    await db["anime"].create_index("tags")
    await db["anime"].create_index("year")
    await db["characters"].create_index("name")
    await db["characters"].create_index("anime_ids")
    await db["characters"].create_index("tags")
    await db["characters"].create_index("gender")
    await db["characters"].create_index("role")
    await db["relationships"].create_index("source_id")
    await db["relationships"].create_index("target_id")
    await db["relationships"].create_index("relationship")
    await db["relationships"].create_index("type")
    await db["events"].create_index(
        [
            ("month", 1),
            ("day", 1)
        ]
    )

    await db["events"].create_index(
        "event_type"
    )

    await db["events"].create_index(
        "anime_id"
    )

    await db["events"].create_index(
        "manga_id"
    )

    # News pipeline indexes
    await db["news"].create_index("url", unique=True)
    await db["news"].create_index("category")
    await db["news"].create_index("published_at")

    print("✅ MongoDB Connected")


async def close_db():
    global client

    if client:
        client.close()
        print("❌ MongoDB Disconnected")


def get_db():
    if client is None:
        raise RuntimeError("MongoDB client is not connected")

    return client["anime_ai"]


def get_anime_collection():
    db = get_db()
    return db["anime"]

def get_relationship_collection():
    db = get_db()
    return db["relationships"]