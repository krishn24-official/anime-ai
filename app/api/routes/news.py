from fastapi import APIRouter, HTTPException, Query

from app.services.news_service import (
    fetch_latest_news,
    fetch_news_by_category,
    fetch_news_detail,
)
from app.services.news_pipeline_service import run_news_pipeline

router = APIRouter(
    prefix="/news",
    tags=["News"]
)


@router.get("/latest")
async def get_latest_news(limit: int = Query(5, ge=1, le=20)):
    return await fetch_latest_news(limit=limit)


@router.get("")
async def get_news(
    category: str | None = Query(None, description="Anime, Games, Movies, TV Series"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    start_date: str | None = Query(None, description="Start date in ISO format or YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date in ISO format or YYYY-MM-DD"),
    search: str | None = Query(None, description="Search term for title and summary"),
    source: str | None = Query(None, description="Exact match for source"),
):
    return await fetch_news_by_category(
        category=category, 
        page=page, 
        limit=limit,
        start_date=start_date,
        end_date=end_date,
        search=search,
        source=source,
    )


@router.get("/{news_id}")
async def get_news_detail(news_id: str):
    article = await fetch_news_detail(news_id)

    if not article:
        raise HTTPException(status_code=404, detail="News article not found")

    return article


@router.post("/run")
async def trigger_news_pipeline():
    return await run_news_pipeline()