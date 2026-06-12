from app.db.mongo import get_db


async def get_relationship_between(
    id_a: str,
    id_b: str
):
    """
    Returns all relationship docs connecting id_a and id_b,
    in either direction (a->b or b->a).
    """

    db = get_db()

    return await (
        db["relationships"]
        .find(
            {
                "is_deleted": False,
                "$or": [
                    {"source_id": id_a, "target_id": id_b},
                    {"source_id": id_b, "target_id": id_a}
                ]
            }
        )
        .to_list(None)
    )


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


async def get_relationships_by_target(
    target_id: str,
    relationship: str = None,
    type_: str = None
):

    query = {
        "target_id": target_id,
        "is_deleted": False
    }

    if relationship:
        query["relationship"] = relationship

    if type_:
        query["type"] = type_

    db = get_db()

    return await (
        db["relationships"]
        .find(query)
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