from app.db.mongo import get_db


async def get_relationship_between(id_a: str, id_b: str):
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
                    {"source_id": id_b, "target_id": id_a},
                ],
            }
        )
        .to_list(None)
    )


async def get_relationships_by_source(source_id: str):

    db = get_db()

    return await (
        db["relationships"]
        .find({"source_id": source_id, "is_deleted": False})
        .to_list(None)
    )


async def get_relationships_by_target(
    target_id: str, relationship: str = None, type_: str = None
):

    query = {"target_id": target_id, "is_deleted": False}

    if relationship:
        query["relationship"] = relationship

    if type_:
        query["type"] = type_

    db = get_db()

    return await db["relationships"].find(query).to_list(None)


async def get_relationships_by_type(source_id: str, relationship_type: str):

    db = get_db()

    return await (
        db["relationships"]
        .find({"source_id": source_id, "type": relationship_type, "is_deleted": False})
        .to_list(None)
    )


async def find_exact_relationship(source_id: str, target_id: str, relationship: str):
    from app.services.relationship_admin_service import _make_rel_id

    db = get_db()
    expected_id = _make_rel_id(source_id, target_id, relationship)

    return await db["relationships"].find_one({"_id": expected_id, "is_deleted": False})


async def search_relationship_entities(
    query: str, limit: int = 10, types_list: list[str] = None
):
    """Entities (characters, organizations, titles) matching `query`, for the admin
    relationship picker. Uses the shared ranked search; best matches first per type."""
    import asyncio

    from app.container import search_service
    from app.domain.search.entities import KIND_BY_CONTENT_TYPE

    entity_types = ["character", "organization", "anime", "manga", "movie", "tv_series"]
    if types_list is not None:
        entity_types = [t for t in entity_types if t in types_list]

    pages = await asyncio.gather(
        *(
            search_service().search_kind(query, KIND_BY_CONTENT_TYPE[t], limit)
            for t in entity_types
        )
    )
    results = [
        {"id": doc.id, "name": doc.title, "entity_type": t, "image": doc.image or ""}
        for t, (docs, _) in zip(entity_types, pages)
        for doc in docs
    ]
    return results[:limit]

