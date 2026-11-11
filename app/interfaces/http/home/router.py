"""HTTP endpoints for the home page."""

from fastapi import APIRouter, Depends, Query

from app.application.home.service import HomeService
from app.container import home_service
from app.interfaces.http.home.schemas import HeroSlideResponse

router = APIRouter(prefix="/home", tags=["Home"])


@router.get("/hero", response_model=list[HeroSlideResponse])
async def hero_feed(
    limit: int = Query(7, ge=1, le=12), service: HomeService = Depends(home_service)
):
    return [HeroSlideResponse.from_domain(s) for s in await service.hero_feed(limit)]
