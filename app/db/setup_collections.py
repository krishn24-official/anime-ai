from app.db.mongo import get_db

COLLECTIONS = [
    "characters",
    "relationships",
    "manga",
    "chapters",
    "anime",
    "episodes",
    "voice_actors",
    "news",
    "users",
    "refresh_tokens",
    "movies",
    "tv_series",
    "ratings",
    "watchlist",
    "comments",
    "tier_lists",
    "organizations",
]

async def create_collections():
    db = get_db()
    existing = await db.list_collection_names()

    for name in COLLECTIONS:
        if name not in existing:
            await db.create_collection(name)
            print(f"✅ Created collection: {name}")
        else:
            print(f"ℹ️ Exists: {name}")