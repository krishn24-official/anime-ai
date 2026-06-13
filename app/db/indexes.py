from app.db.mongo import get_db

async def create_indexes():
    db = get_db()

    # characters
    await db.characters.create_index("name")
    await db.characters.create_index([("birth_month", 1), ("birth_day", 1)])

    # relationships
    await db.relationships.create_index("source_id")
    await db.relationships.create_index("target_id")
    await db.relationships.create_index("relationship")

    # manga / chapters
    await db.manga.create_index("name")
    await db.chapters.create_index("manga_id")
    await db.chapters.create_index("chapter_number")

    # anime / episodes
    await db.anime.create_index("name")
    await db.episodes.create_index("anime_id")
    await db.episodes.create_index("episode_number")

    # voice actors
    await db.voice_actors.create_index("name")

    # news
    await db.news.create_index("url", unique=True)
    await db.news.create_index("category")
    await db.news.create_index("published_at")

    print("⚡ Indexes created")