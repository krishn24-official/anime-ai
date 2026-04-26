from motor.motor_asyncio import AsyncIOMotorClient
from app.config import MONGO_URI

client = None

async def connect_db():
    global client
    if not MONGO_URI:
        raise RuntimeError("MONGO_URI is not set")
    client = AsyncIOMotorClient(MONGO_URI)
    print("✅ MongoDB Connected:")


async def close_db():
    global client
    if client:
        client.close()
        print("❌ MongoDB Disconnected")


def get_db():
    if client is None:
        raise RuntimeError("MongoDB client is not connected")
    return client["anime_ai"]

