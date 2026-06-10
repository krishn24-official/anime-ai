from fastapi import (
    APIRouter,
    HTTPException
)

from app.services.anime_service import (
    fetch_all_anime,
    fetch_anime,
    fetch_anime_search,
    fetch_anime_characters,
    fetch_anime_details
)

router = APIRouter(
    prefix="/anime",
    tags=["Anime"]
)

@router.get("")
async def get_anime():

    return await (
        fetch_all_anime()
    )

@router.get(
    "/{anime_id}"
)
async def get_anime_by_id(
    anime_id: str
):

    anime = await (
        fetch_anime(
            anime_id
        )
    )

    if not anime:

        raise HTTPException(
            status_code=404,
            detail="Anime not found"
        )

    return anime

@router.get(
    "/search/{query}"
)
async def search(
    query: str
):

    return await (
        fetch_anime_search(
            query
        )
    )

@router.get(
    "/{anime_id}/characters"
)
async def get_anime_characters(
    anime_id: str
):

    return await (
        fetch_anime_characters(
            anime_id
        )
    )

@router.get(
    "/{anime_id}/details"
)
async def get_anime_details(
    anime_id: str
):

    anime = await (
        fetch_anime_details(
            anime_id
        )
    )

    if not anime:

        raise HTTPException(
            status_code=404,
            detail="Anime not found"
        )

    return anime
