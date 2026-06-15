from fastapi import APIRouter, HTTPException, Query

from app.services.movie_service import fetch_all_movies, fetch_movie

router = APIRouter(
    prefix="/movies",
    tags=["Movies"]
)


@router.get("")
async def get_movies(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
):
    return await fetch_all_movies(page=page, limit=limit)


@router.get("/{movie_id}")
async def get_movie(movie_id: str):
    movie = await fetch_movie(movie_id)

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    return movie