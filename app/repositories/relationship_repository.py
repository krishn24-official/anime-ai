from app.db.mongo import get_db


async def get_relationships_by_source(
    source_id: str
):

    db = get_db()

    return await (
        db["relationships"]
        .find(
            {
                "source_id": source_id,
                "is_deleted": False
            }
        )
        .to_list(None)
    )


async def get_relationships_by_type(
    source_id: str,
    relationship_type: str
):

    db = get_db()

    return await (
        db["relationships"]
        .find(
            {
                "source_id": source_id,
                "type": relationship_type,
                "is_deleted": False
            }
        )
        .to_list(None)
    )