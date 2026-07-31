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
    
    # We also need to fetch their filmography!
    # Let's query content where this actor's name is in the 'actors' array
    from app.db.mongo import get_db
    db = get_db()
    search_query = {
        "$or": [
            {"cast.actor_id": actor["_id"]},
            {"director.actor_id": actor["_id"]},
            {"creators.actor_id": actor["_id"]},
            {"actors": actor["name"]},
            {"director": actor["name"]},
            {"crew": actor["name"]},
            {"producers": actor["name"]}
        ],
        "is_deleted": False
    }
    movies = await db["movies"].find(search_query).to_list(None)
    tv = await db["tv_series"].find(search_query).to_list(None)
    
    # For now, let's just return the actor and let the frontend do what it wants or format it here.
    # To match screenshot, maybe we return filmography as a list of content
    actor["filmography"] = []
    
    for m in movies:
        actor["filmography"].append({
            "id": m["_id"],
            "title": m.get("title"),
            "year": m.get("year"),
            "content_type": "movie",
            "poster": m.get("images", {}).get("poster")
        })
        
    for t in tv:
        actor["filmography"].append({
            "id": t["_id"],
            "title": t.get("title"),
            "year": t.get("year"),
            "content_type": "tv_series",
            "poster": t.get("images", {}).get("poster")
        })
    
    # Safely convert year to int for sorting, defaulting to 0
    def safe_year(x):
        y = x.get("year")
        if not y:
            return 0
        try:
            return int(y)
        except (ValueError, TypeError):
            return 0

    # Sort filmography by year descending
    actor["filmography"].sort(key=safe_year, reverse=True)
    
    return actor
