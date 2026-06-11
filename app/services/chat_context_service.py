from app.services.character_service import (
    fetch_character_details
)


async def build_character_context(
    character_id: str
):

    details = await (
        fetch_character_details(
            character_id
        )
    )

    if not details:
        return None

    return details