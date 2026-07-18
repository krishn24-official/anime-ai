from app.db.mongo import get_db
from app.db.index_utils import create_index_safely

async def create_indexes():
    db = get_db()

    # characters
        # characters
    await create_index_safely(db.characters, "name")
    await create_index_safely(db.characters, [("name", "text")])          # ADD
    await create_index_safely(db.characters, "game_properties")           # ADD
    await create_index_safely(db.characters, [("birth_month", 1), ("birth_day", 1)])

    # relationships
    await create_index_safely(db.relationships, "source_id")
    await create_index_safely(db.relationships, "target_id")
    await create_index_safely(db.relationships, "relationship")

    # manga / chapters
    await create_index_safely(db.manga, "name")
    await create_index_safely(
        db.chapters, 
        [("manga_id", 1), ("chapter_number", 1)], 
        unique=True
    )

    # anime / episodes
    await create_index_safely(db.anime, "title.english")                  # CHANGED
    await create_index_safely(db.anime, "title.romaji")                   # CHANGED
    
    try:
        await db.episodes.drop_index("anime_id_1")
    except Exception:
        pass
    try:
        await db.episodes.drop_index("episode_number_1")
    except Exception:
        pass

    await create_index_safely(
        db.episodes, 
        [("anime_id", 1), ("episode_number", 1)], 
        unique=True,
        partialFilterExpression={"anime_id": {"$type": "string"}}
    )
    await create_index_safely(
        db.episodes, 
        [("tv_series_id", 1), ("episode_number", 1)], 
        unique=True,
        partialFilterExpression={"tv_series_id": {"$type": "string"}}
    )

    # voice actors
    await create_index_safely(db.voice_actors, "name")

    # news
    await create_index_safely(db.news, "url", unique=True, sparse=True)
    await create_index_safely(db.news, "category")
    await create_index_safely(db.news, "published_at")
    await create_index_safely(db.news, [("category", 1), ("published_at", -1)])  # ADD
    await create_index_safely(db.news, "source")

    # organizations
    await create_index_safely(db.organizations, "name")                   # REMOVED unique=True
    await create_index_safely(db.organizations, "type")
    await create_index_safely(db.organizations, "anime_ids")
    await create_index_safely(db.organizations, "manga_id")

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

    # organizations
    await create_index_safely(db.organizations, "name", unique=True)
    await create_index_safely(db.organizations, "type")
    await create_index_safely(db.organizations, "anime_ids")
    await create_index_safely(db.organizations, "manga_id")

    # trending
    await create_index_safely(
        db.trending,
        [("content_type", 1), ("content_id", 1)],
        unique=True
    )
    await create_index_safely(db.trending, [("pinned", -1), ("score", -1)])
    await create_index_safely(
        db.trending,
        "expires_at",
        expireAfterSeconds=0
    )

    # trending_mentions
    await create_index_safely(db.trending_mentions, [("content_id", 1), ("matched_at", -1)])
    await create_index_safely(
        db.trending_mentions,
        [("content_id", 1), ("news_id", 1)],
        unique=True
    )
    await create_index_safely(
        db.trending_mentions,
        "matched_at",
        expireAfterSeconds=172800  # 48 hours
    )

    # search_logs
    await create_index_safely(db.search_logs, [("content_id", 1), ("searched_at", -1)])
    await create_index_safely(
        db.search_logs,
        "searched_at",
        expireAfterSeconds=10800  # 3 hours
    )

    # actors
    await create_index_safely(db.actors, "name")

    print("Indexes created")