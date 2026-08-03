import asyncio
from app.db.mongo import get_db, connect_db, close_db

async def main():
    await connect_db()
    db = get_db()
    
    docs = await db["manga"].find({"_id": {"$in": ["manga_boruto-naruto-next-generations"]}}).to_list(None)
    print("Found docs:", docs)
    
    # Try finding the top 50 manga sorted by _id -1
    cursor = db["manga"].find({"is_deleted": {"$ne": True}}).sort("_id", -1).limit(50)
    items = await cursor.to_list(None)
    ids = [str(item["_id"]) for item in items]
    print("Fallback IDs include boruto?", "manga_boruto-naruto-next-generations" in ids)
    
    # See if rating repository has boruto
    ratings = await db["ratings"].find({"content_id": "manga_boruto-naruto-next-generations"}).to_list(None)
    print("Ratings for boruto:", ratings)
    
    await close_db()

asyncio.run(main())
