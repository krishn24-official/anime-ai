import asyncio
from pymongo import AsyncMongoClient
from app.config import MONGO_URI, MONGO_DB_NAME

async def main():
    client = AsyncMongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]
    pipeline = [{"$limit": 5}]
    
    # Let's inspect aggregate
    cursor = db["trending"].aggregate(pipeline)
    print("Cursor type:", type(cursor))
    
    if hasattr(cursor, "__await__"):
        print("Cursor is a coroutine!")
        cursor = await cursor
        print("After await:", type(cursor))
        
    try:
        res = await cursor.to_list(None)
        print("Got results:", len(res))
    except Exception as e:
        print("Error:", repr(e))

asyncio.run(main())
