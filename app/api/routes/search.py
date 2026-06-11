from fastapi import (
    APIRouter,
    Query
)

from app.services.search_service import (
    global_search
)

router = APIRouter(
    prefix="/search",
    tags=["Search"]
)


@router.get("")
async def search(
    q: str = Query(...)
):

    return await (
        global_search(q)
    )