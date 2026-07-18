from app.repositories.actors_repository import get_all_actors, get_actor_by_id, search_actors

async def fetch_all_actors(include_deleted: bool = False, search: str = None, limit: int = 50, skip: int = 0):
    return await get_all_actors(include_deleted, search, limit, skip)

async def fetch_actor(actor_id: str):
    return await get_actor_by_id(actor_id)

async def search_actor(query: str):
    if not query or len(query) < 2:
        return []
    return await search_actors(query)
