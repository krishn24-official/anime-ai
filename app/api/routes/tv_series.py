from fastapi import APIRouter, HTTPException, Query

from app.services.tv_series_service import fetch_all_tv_series, fetch_tv_series

router = APIRouter(
    prefix="/tv-series",
    tags=["TV Series"]
)


@router.get("")
async def get_tv_series_list(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
):
    return await fetch_all_tv_series(page=page, limit=limit)


@router.get("/{series_id}")
async def get_tv_series(series_id: str):
    series = await fetch_tv_series(series_id)

    if not series:
        raise HTTPException(status_code=404, detail="TV series not found")

    return series