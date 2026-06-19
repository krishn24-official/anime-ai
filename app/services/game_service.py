from app.repositories.game_repository import get_playable_characters
from app.services.game_properties import GAME_QUESTIONS


def _serialize_character(char: dict) -> dict:
    images = char.get("images") or {}
    return {
        "id": str(char["_id"]),
        "name": char.get("name"),
        "image": images.get("profile") or images.get("poster"),
        "anime_ids": char.get("anime_ids", []),
        "game_properties": char.get("game_properties", []),
    }


async def fetch_game_characters():
    """Returns all playable characters with their game properties."""
    characters = await get_playable_characters()

    return {
        "characters": [_serialize_character(c) for c in characters],
        "questions": GAME_QUESTIONS,
        "total": len(characters),
    }