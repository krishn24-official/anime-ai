from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import get_current_user, get_optional_user
from app.services import tier_list_service

router = APIRouter(
    prefix="/tier-lists",
    tags=["Tier Lists"]
)


class TierItem(BaseModel):
    content_type: str   # character, anime, manga, movie, tv_series
    content_id: str
    name: str | None = None     # display name, optional cache
    image: str | None = None    # display image, optional cache


class Tier(BaseModel):
    name: str
    color: str = "#888888"   # hex color
    items: list[TierItem] = []


class CreateTierListRequest(BaseModel):
    name: str
    tiers: list[Tier]
    is_public: bool = True


class UpdateTierListRequest(BaseModel):
    name: str | None = None
    tiers: list[Tier] | None = None
    is_public: bool | None = None


@router.post("")
async def create_tier_list(
    payload: CreateTierListRequest,
    current_user: dict = Depends(get_current_user),
):
    tiers_data = [t.model_dump() for t in payload.tiers]

    result, error = await tier_list_service.create_new_tier_list(
        user_id=current_user["_id"],
        name=payload.name,
        tiers=tiers_data,
        is_public=payload.is_public,
    )

    if error:
        raise HTTPException(status_code=400, detail=error)

    return result


@router.get("/my")
async def get_my_tier_lists(current_user: dict = Depends(get_current_user)):
    return await tier_list_service.fetch_user_tier_lists(current_user["_id"])


@router.get("/public")
async def get_public_tier_lists(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
):
    return await tier_list_service.fetch_public_tier_lists(page=page, limit=limit)


@router.get("/search")
async def search_content(
    q: str = Query(..., min_length=2),
    content_type: str | None = Query(None, description="character, anime, manga, movie, tv_series"),
):
    """Search for characters/anime/manga/movies/tv_series to add to a tier list."""
    return await tier_list_service.search_content_for_tier_list(q, content_type)


@router.get("/{tier_list_id}")
async def get_tier_list(
    tier_list_id: str,
    current_user: dict | None = Depends(get_optional_user),
):
    user_id = current_user["_id"] if current_user else None

    result, error = await tier_list_service.fetch_tier_list(tier_list_id, user_id)

    if error:
        status_code = 404 if "not found" in error.lower() else 403
        raise HTTPException(status_code=status_code, detail=error)

    return result


@router.put("/{tier_list_id}")
async def update_tier_list(
    tier_list_id: str,
    payload: UpdateTierListRequest,
    current_user: dict = Depends(get_current_user),
):
    tiers_data = [t.model_dump() for t in payload.tiers] if payload.tiers is not None else None

    result, error = await tier_list_service.update_existing_tier_list(
        tier_list_id=tier_list_id,
        user_id=current_user["_id"],
        name=payload.name,
        tiers=tiers_data,
        is_public=payload.is_public,
    )

    if error:
        raise HTTPException(status_code=400, detail=error)

    return result


@router.delete("/{tier_list_id}")
async def delete_tier_list(
    tier_list_id: str,
    current_user: dict = Depends(get_current_user),
):
    success, error = await tier_list_service.delete_existing_tier_list(
        tier_list_id=tier_list_id,
        user_id=current_user["_id"],
    )

    if not success:
        raise HTTPException(status_code=404, detail=error)

    return {"message": "Tier list deleted"}