from fastapi import (
    APIRouter,
    HTTPException
)

from app.services.manga_service import (
    fetch_all_manga,
    fetch_manga,
    fetch_manga_search,
    fetch_manga_summary,
    fetch_manga_details
)

router = APIRouter(
    prefix="/manga",
    tags=["Manga"]
)

@router.get("")
async def get_manga():

    return await (
        fetch_all_manga()
    )

@router.get(
    "/search/{query}"
)
async def search(
    query: str
):

    return await (
        fetch_manga_search(
            query
        )
    )

@router.get(
    "/{manga_id}"
)
async def get_manga_by_id(
    manga_id: str
):

    manga = await (
        fetch_manga(
            manga_id
        )
    )

    if not manga:

        raise HTTPException(
            status_code=404,
            detail="Manga not found"
        )

    return manga

@router.get(
    "/{manga_id}/summary"
)
async def get_summary(
    manga_id: str
):

    manga = await (
        fetch_manga_summary(
            manga_id
        )
    )

    if not manga:

        raise HTTPException(
            status_code=404,
            detail="Manga not found"
        )

    return manga

@router.get(
    "/{manga_id}/details"
)
async def get_details(
    manga_id: str
):

    manga = await (
        fetch_manga_details(
            manga_id
        )
    )

    if not manga:

        raise HTTPException(
            status_code=404,
            detail="Manga not found"
        )

    return manga

