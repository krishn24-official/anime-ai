from app.db.mongo import get_db


async def check_db():
    try:
        db = get_db()
        collections = await db.list_collection_names()
        print("📦 Collections:", collections)
        return True
    except Exception as e:
        print("❌ DB Error:", e)
        return False