"""GET /search: global search across anime, movies, TV, manga, characters, actors
and organizations.

Response (public contract): one list per kind with that kind's display fields,
plus `top_result` ({"kind", "id"} of the best match overall, or null).
"""

from fastapi import APIRouter, Depends, Query

from app.application.search.service import SearchService
from app.container import search_service

router = APIRouter(tags=["Search"])


@router.get("/search")
async def search(q: str = Query(...), service: SearchService = Depends(search_service)):
    results = await service.search(q)
    body: dict = {
        kind: [hit.document.display for hit in hits] for kind, hits in results.by_kind.items()
    }
    top = results.top
    body["top_result"] = {"kind": top.document.kind, "id": top.document.id} if top else None
    return body
