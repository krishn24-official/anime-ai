from app.repositories.voice_actors_repository import (
    get_voice_actor_by_id,
    get_voice_actor_filmography
)

async def fetch_voice_actor(voice_actor_id: str):
    return await get_voice_actor_by_id(voice_actor_id)

async def fetch_voice_actor_filmography(voice_actor_id: str):
    return await get_voice_actor_filmography(voice_actor_id)
