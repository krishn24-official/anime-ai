from fastapi import (
    APIRouter,
    Query,
    Depends
)
from fastapi.responses import Response
from pydantic import BaseModel
from app.api.deps import get_current_user
from app.repositories import trending_repository

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

class LogSearchClickRequest(BaseModel):
    content_type: str
    content_id: str
    query: str

@router.post("/log-click")
async def log_search_click(
    req: LogSearchClickRequest,
    user: dict = Depends(get_current_user)
):
    await trending_repository.record_search_click(
        req.content_type,
        req.content_id,
        req.query,
        str(user["_id"])
    )
    return Response(status_code=202)