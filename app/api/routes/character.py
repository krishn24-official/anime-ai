from fastapi import (
    APIRouter,
    HTTPException
)

from app.services.character_service import (
    fetch_all_characters,
    fetch_character,
    search_character,
    fetch_character_details,
    fetch_character_summary
)

router = APIRouter(
    prefix="/characters",
    tags=["Characters"]
)

@router.get("")

async def get_characters():

    return await (
        fetch_all_characters()
    )

@router.get("/{character_id}")

async def get_character(
    character_id: str
):

    character = await (
        fetch_character(
            character_id
        )
    )

    if not character:

        raise HTTPException(
            status_code=404,
            detail="Character not found"
        )

    return character

@router.get("/search/{query}")

async def search(
    query: str
):

    return await (
        search_character(query)
    )

@router.get(
    "/{character_id}/details"
)
async def get_character_details(
    character_id: str
):

    details = await (
        fetch_character_details(
            character_id
        )
    )

    if not details:

        raise HTTPException(
            status_code=404,
            detail="Character not found"
        )

    return details

@router.get(
    "/{character_id}/summary"
)
async def get_character_summary(
    character_id: str
):

    summary = await (
        fetch_character_summary(
            character_id
        )
    )

    if not summary:

        raise HTTPException(
            status_code=404,
            detail="Character not found"
        )

    return summary