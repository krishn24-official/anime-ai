from fastapi import (
    APIRouter,
    HTTPException,
    Query
)

from app.services.character_service import (
    fetch_all_characters,
    fetch_character,
    search_character,
    fetch_character_details,
    fetch_character_summary,
    fetch_birthdays_by_date_range
)

router = APIRouter(
    prefix="/characters",
    tags=["Characters"]
)

@router.get("")
async def get_characters(
    skip: int = Query(0, ge=0, description="Number of characters to skip"),
    limit: int = Query(50, ge=1, le=200, description="Number of characters to return (max 200)"),
):
    items = await fetch_all_characters(skip=skip, limit=limit)
    return {
        "items": items,
        "skip": skip,
        "limit": limit,
        "has_more": len(items) == limit,
    }


@router.get("/birthdays/range")
async def get_birthdays_range(
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(..., description="End date in YYYY-MM-DD format")
):
    return await fetch_birthdays_by_date_range(start_date, end_date)

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