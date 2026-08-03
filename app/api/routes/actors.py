from fastapi import APIRouter, HTTPException, Query
from app.services.actors_service import fetch_all_actors, fetch_actor, search_actor, fetch_birthdays_by_date_range

router = APIRouter(
    prefix="/actors",
    tags=["Actors"]
)

@router.get("")
async def get_actors(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=1000)
):
    skip = (page - 1) * limit
    return await fetch_all_actors(limit=limit, skip=skip)

@router.get("/birthdays/range")
async def get_birthdays_range(
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(..., description="End date in YYYY-MM-DD format")
):
    return await fetch_birthdays_by_date_range(start_date, end_date)

@router.get("/search/{query}")
async def search(query: str):
    return await search_actor(query)

@router.get("/{actor_id}")
async def get_actor(actor_id: str):
    actor = await fetch_actor(actor_id)
    if not actor:
        raise HTTPException(status_code=404, detail="Actor not found")
    
    from app.services.actors_service import fetch_actor_filmography
    actor["filmography"] = await fetch_actor_filmography(actor)
    
    return actor
