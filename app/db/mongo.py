from pymongo import AsyncMongoClient
from app.config import MONGO_URI, MONGO_DB_NAME

client = None


async def connect_db():
    global client

    if not MONGO_URI:
        raise RuntimeError("MONGO_URI is not set")

    client = AsyncMongoClient(MONGO_URI)

    db = client[MONGO_DB_NAME]

    from app.db.index_utils import create_index_safely

    # INDEXES
    await create_index_safely(db["anime"], "title.english")
    await create_index_safely(db["anime"], "title.romaji")
    await create_index_safely(db["anime"], "genres")
    await create_index_safely(db["anime"], "tags")
    await create_index_safely(db["anime"], "year")
    await create_index_safely(db["characters"], "name")
    await create_index_safely(db["characters"], "anime_ids")
    await create_index_safely(db["characters"], "tags")
    await create_index_safely(db["characters"], "gender")
    await create_index_safely(db["characters"], "role")
    await create_index_safely(db["relationships"], "source_id")
    await create_index_safely(db["relationships"], "target_id")
    await create_index_safely(db["relationships"], "relationship")
    await create_index_safely(db["relationships"], "type")
    await create_index_safely(
        db["events"],
        [
            ("month", 1),
            ("day", 1)
        ]
    )

    await create_index_safely(
        db["events"],
        "event_type"
    )

    await create_index_safely(
        db["events"],
        "anime_id"
    )

    await create_index_safely(
        db["events"],
        "manga_id"
    )

    # News pipeline indexes
    await create_index_safely(db["news"], "url", unique=True, sparse=True)
    await create_index_safely(db["news"], "category")
    await create_index_safely(db["news"], "published_at")

    print("MongoDB Connected")


async def close_db():
    global client

    if client:
        await client.close()
        print("MongoDB Disconnected")


def get_db():
    if client is None:
        raise RuntimeError("MongoDB client is not connected")

    return client[MONGO_DB_NAME]


def get_anime_collection():
    db = get_db()
    return db["anime"]

def get_relationship_collection():
    db = get_db()
    return db["relationships"]