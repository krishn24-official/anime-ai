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


async def find_exact_relationship(source_id: str, target_id: str, relationship: str):
    from app.services.relationship_admin_service import _make_rel_id
    db = get_db()
    expected_id = _make_rel_id(source_id, target_id, relationship)
    
    return await db["relationships"].find_one({
        "_id": expected_id,
        "is_deleted": False
    })


async def search_relationship_entities(query: str, limit: int = 10, types_list: list[str] = None):
    from app.repositories.search_repository import (
        search_characters, search_organizations, search_anime, 
        search_manga, search_movies, search_tv_series
    )
    import asyncio
    
    tasks = []
    
    # helper to conditionally create tasks
    def should_search(t: str):
        return types_list is None or t in types_list
        
    t_chars = asyncio.create_task(search_characters(query)) if should_search("character") else None
    t_orgs = asyncio.create_task(search_organizations(query)) if should_search("organization") else None
    t_anime = asyncio.create_task(search_anime(query)) if should_search("anime") else None
    t_manga = asyncio.create_task(search_manga(query)) if should_search("manga") else None
    t_movies = asyncio.create_task(search_movies(query)) if should_search("movie") else None
    t_tv = asyncio.create_task(search_tv_series(query)) if should_search("tv_series") else None
    
    results_gather = await asyncio.gather(
        *(t for t in [t_chars, t_orgs, t_anime, t_manga, t_movies, t_tv] if t is not None)
    )
    
    # Reconstruct the results in order
    idx = 0
    chars = results_gather[idx] if t_chars else []; idx += 1 if t_chars else 0
    orgs = results_gather[idx] if t_orgs else []; idx += 1 if t_orgs else 0
    anime = results_gather[idx] if t_anime else []; idx += 1 if t_anime else 0
    manga = results_gather[idx] if t_manga else []; idx += 1 if t_manga else 0
    movies = results_gather[idx] if t_movies else []; idx += 1 if t_movies else 0
    tv = results_gather[idx] if t_tv else []; idx += 1 if t_tv else 0
    
    results = []
    
    for c in chars:
        results.append({
            "id": str(c.get("_id", "")),
            "name": c.get("name", ""),
            "entity_type": "character",
            "image": c.get("images", {}).get("profile", "")
        })
        
    for o in orgs:
        # Some endpoints return "id", some return "_id"
        results.append({
            "id": str(o.get("id", o.get("_id", ""))),
            "name": o.get("name", ""),
            "entity_type": "organization",
            "image": o.get("images", {}).get("logo", "")
        })
        
    for a in anime:
        title = a.get("title", {})
        results.append({
            "id": str(a.get("_id", "")),
            "name": title.get("english") or title.get("romaji", ""),
            "entity_type": "anime",
            "image": a.get("images", {}).get("poster", "")
        })
        
    for m in manga:
        results.append({
            "id": str(m.get("_id", "")),
            "name": m.get("name", ""),
            "entity_type": "manga",
            "image": m.get("cover_image", "")
        })
        
    for mv in movies:
        results.append({
            "id": str(mv.get("_id", "")),
            "name": mv.get("title", ""),
            "entity_type": "movie",
            "image": mv.get("images", {}).get("poster", "")
        })
        
    for t in tv:
        results.append({
            "id": str(t.get("_id", "")),
            "name": t.get("title", ""),
            "entity_type": "tv_series",
            "image": t.get("images", {}).get("poster", "")
        })
        
    return results[:limit]