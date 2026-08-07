import asyncio
from app.db.mongo import connect_db, close_db, get_db

async def test_atlas_search():
    await connect_db()
    db = get_db()
    try:
        # Try a dummy $search query to see if the cluster supports it at all
        # It will fail because index doesn't exist, but the error message will tell us if it's Atlas
        await db["anime"].aggregate([
            {"$search": {"text": {"query": "test", "path": "title.english"}}}
        ]).to_list(None)
    except Exception as e:
        print("Error:", e)
    await close_db()

if __name__ == "__main__":
    asyncio.run(test_atlas_search())
