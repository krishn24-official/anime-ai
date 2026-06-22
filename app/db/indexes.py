from app.db.mongo import get_db
from app.db.index_utils import create_index_safely

async def create_indexes():
    db = get_db()

    # characters
    await create_index_safely(db.characters, "name")
    await create_index_safely(db.characters, [("birth_month", 1), ("birth_day", 1)])

    # relationships
    await create_index_safely(db.relationships, "source_id")
    await create_index_safely(db.relationships, "target_id")
    await create_index_safely(db.relationships, "relationship")

    # manga / chapters
    await create_index_safely(db.manga, "name")
    await create_index_safely(db.chapters, "manga_id")
    await create_index_safely(db.chapters, "chapter_number")

    # anime / episodes
    await create_index_safely(db.anime, "name")
    await create_index_safely(db.episodes, "anime_id")
    await create_index_safely(db.episodes, "episode_number")

    # voice actors
    await create_index_safely(db.voice_actors, "name")

    # news
    await create_index_safely(db.news, "url", unique=True, sparse=True)
    await create_index_safely(db.news, "category")
    await create_index_safely(db.news, "published_at")

    # users
    await create_index_safely(db.users, "email", unique=True)
    await create_index_safely(db.users, "username", unique=True, sparse=True)
    await create_index_safely(db.users, "is_admin")

    # news (manual posts use source field to distinguish from RSS-fetched)
    await create_index_safely(db.news, "source")

    # refresh tokens
    await create_index_safely(db.refresh_tokens, "token", unique=True)
    await create_index_safely(db.refresh_tokens, "user_id")
    await create_index_safely(
        db.refresh_tokens,
        "expires_at",
        expireAfterSeconds=0   # MongoDB TTL index — auto-deletes expired tokens
    )

    # ratings
    await create_index_safely(
        db.ratings,
        [("user_id", 1), ("content_type", 1), ("content_id", 1)],
        unique=True
    )
    await create_index_safely(db.ratings, [("content_type", 1), ("content_id", 1)])

    # watchlist
    await create_index_safely(
        db.watchlist,
        [("user_id", 1), ("content_type", 1), ("content_id", 1)],
        unique=True
    )

    # comments
    await create_index_safely(db.comments, [("content_type", 1), ("content_id", 1)])
    await create_index_safely(db.comments, "parent_id")

    # movies / tv_series
    await create_index_safely(db.movies, "title")
    await create_index_safely(db.tv_series, "title")

    # tier lists
    await create_index_safely(db.tier_lists, "user_id")
    await create_index_safely(db.tier_lists, "is_public")
    await create_index_safely(db.tier_lists, [("is_public", 1), ("updated_at", -1)])

    print("⚡ Indexes created")