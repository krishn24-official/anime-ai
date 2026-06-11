from app.db.mongo import get_db


async def get_database_stats():

    db = get_db()

    anime_count = await (
        db["anime"]
        .count_documents(
            {
                "is_deleted": False
            }
        )
    )

    character_count = await (
        db["characters"]
        .count_documents(
            {
                "is_deleted": False
            }
        )
    )

    relationship_count = await (
        db["relationships"]
        .count_documents(
            {
                "is_deleted": False
            }
        )
    )

    manga_count = await (
        db["manga"]
        .count_documents(
            {
                "is_deleted": False
            }
        )
    )

    return {

        "anime_count":
            anime_count,

        "character_count":
            character_count,

        "relationship_count":
            relationship_count,

        "manga_count":
            manga_count
    }