from fastapi import APIRouter, HTTPException
from app.services.voice_actors_service import fetch_voice_actor, fetch_voice_actor_filmography

router = APIRouter(
    prefix="/voice-actors",
    tags=["Voice Actors"]
)

@router.get("/{voice_actor_id}")
async def get_voice_actor(voice_actor_id: str):
    actor = await fetch_voice_actor(voice_actor_id)
    if not actor:
        raise HTTPException(status_code=404, detail="Voice Actor not found")
    
    # We return the filmography under a flat array for the UI
    actor["filmography"] = await fetch_voice_actor_filmography(voice_actor_id)
    
    return actor
