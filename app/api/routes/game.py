from fastapi import APIRouter

from app.services.game_service import fetch_game_characters

router = APIRouter(
    prefix="/game",
    tags=["Game"]
)


@router.get("/characters")
async def get_game_characters():
    """
    Returns all characters with game_properties for the Akinator-style game.
    Also returns the questions list.

    Frontend uses this to:
    1. Load all character data once at game start
    2. Run the getBestQuestion algorithm locally (no server round-trips per answer)
    3. Narrow down candidates based on Yes/No answers
    """
    return await fetch_game_characters()