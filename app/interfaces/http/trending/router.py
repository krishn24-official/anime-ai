"""HTTP endpoints for trending. Thin: parse input, call the use case, shape output."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response

from app.api.deps import get_current_admin, get_current_user
from app.application.trending.service import TrendingService
from app.container import trending_service
from app.interfaces.http.trending.schemas import (
    SearchClickRequest,
    StatusResponse,
    TrendingItemResponse,
)

router = APIRouter(tags=["Trending"])


@router.get("/content/trending", response_model=list[TrendingItemResponse])
async def list_trending(
    limit: int = 10, service: TrendingService = Depends(trending_service)
):
    return [TrendingItemResponse.from_domain(i) for i in await service.list_trending(limit)]


@router.post("/search/log-click", status_code=202)
async def log_search_click(
    req: SearchClickRequest,
    user: dict = Depends(get_current_user),
    service: TrendingService = Depends(trending_service),
):
    await service.record_search_click(
        req.content_type, req.content_id, req.query, str(user["_id"])
    )
    return Response(status_code=202)


# ── Admin ─────────────────────────────────────────────────────────────────────


@router.get("/admin/trending", response_model=list[TrendingItemResponse])
async def admin_list_trending(
    current_admin: dict = Depends(get_current_admin),
    service: TrendingService = Depends(trending_service),
):
    items = await service.list_trending(limit=100)
    return [TrendingItemResponse.from_domain(i) for i in items]


@router.post("/admin/trending", response_model=StatusResponse)
async def admin_pin(
    content_type: str = Form(...),
    content_id: str = Form(...),
    note: Optional[str] = Form(None),
    expires_at: Optional[datetime] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_admin: dict = Depends(get_current_admin),
    service: TrendingService = Depends(trending_service),
):
    image_bytes = None
    if image:
        image_bytes = await image.read() or None  # an empty upload counts as no image

    await service.pin(
        content_type=content_type,
        content_id=content_id,
        admin_id=str(current_admin["_id"]),
        note=note,
        expires_at=expires_at,
        image_bytes=image_bytes,
    )
    return StatusResponse()


@router.delete("/admin/trending/{content_type}/{content_id}", response_model=StatusResponse)
async def admin_unpin(
    content_type: str,
    content_id: str,
    current_admin: dict = Depends(get_current_admin),
    service: TrendingService = Depends(trending_service),
):
    await service.unpin(content_type, content_id)
    return StatusResponse()
