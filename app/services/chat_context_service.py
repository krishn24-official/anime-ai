from app.services.character_service import (
    fetch_character_details
)


async def build_character_context(
    character_or_id
):
    if isinstance(character_or_id, dict):
        character_id = str(character_or_id.get("_id", ""))
    else:
        character_id = str(character_or_id)

    details = await (
        fetch_character_details(
            character_id
        )
    )

    if not details:
        return None

    return details