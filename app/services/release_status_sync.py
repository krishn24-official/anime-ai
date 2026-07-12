import calendar
from datetime import datetime, timezone, date
from app.db.mongo import get_db

def _get_window_end_date(year: int, month: int | None) -> date:
    if month:
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, last_day)
    return date(year, 12, 31)

async def sync_anime_release_status():
    db = get_db()
    today = datetime.now(timezone.utc).date()
    
    auto_released = 0
    flagged_for_review = 0
    
    # Only look at upcoming anime that aren't deleted
    cursor = db["anime"].find({"status": "upcoming", "is_deleted": {"$ne": True}})
    
    async for doc in cursor:
        rd = doc.get("release_date")
        if not rd:
            continue
            
        precision = rd.get("precision")
        y = rd.get("year")
        m = rd.get("month")
        d = rd.get("day")
        
        if precision == "day" and y and m and d:
            release_d = date(y, m, d)
            if release_d <= today:
                await db["anime"].update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"status": "ongoing", "needs_release_review": False}}
                )
                auto_released += 1
                
        elif precision in ("month", "year") and y:
            window_end = _get_window_end_date(y, m if precision == "month" else None)
            if today > window_end:
                if not doc.get("needs_release_review"):
                    await db["anime"].update_one(
                        {"_id": doc["_id"]},
                        {"$set": {"needs_release_review": True}}
                    )
                    flagged_for_review += 1
                    
    return {"auto_released": auto_released, "flagged_for_review": flagged_for_review}

async def sync_movie_release_status():
    db = get_db()
    today = datetime.now(timezone.utc).date()
    today_str = today.strftime("%Y-%m-%d")
    
    auto_released = 0
    flagged_for_review = 0
    
    non_released_statuses = ["Planned", "In Production", "Post Production", "Rumored"]
    
    cursor = db["movies"].find({
        "status": {"$in": non_released_statuses},
        "is_deleted": {"$ne": True}
    })
    
    async for doc in cursor:
        rd_str = doc.get("release_date")
        rp = doc.get("release_precision")
        
        if rd_str:
            # It has a specific string release date
            if rd_str <= today_str:
                await db["movies"].update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"status": "Released", "needs_release_review": False}}
                )
                auto_released += 1
        elif rp:
            # It has coarse precision
            precision = rp.get("precision")
            y = rp.get("year")
            m = rp.get("month")
            if precision in ("month", "year") and y:
                window_end = _get_window_end_date(y, m if precision == "month" else None)
                if today > window_end:
                    if not doc.get("needs_release_review"):
                        await db["movies"].update_one(
                            {"_id": doc["_id"]},
                            {"$set": {"needs_release_review": True}}
                        )
                        flagged_for_review += 1
                        
    return {"auto_released": auto_released, "flagged_for_review": flagged_for_review}

async def sync_tv_series_release_status():
    db = get_db()
    today = datetime.now(timezone.utc).date()
    today_str = today.strftime("%Y-%m-%d")
    
    auto_released = 0
    flagged_for_review = 0
    
    non_released_statuses = ["Planned", "In Production", "Pilot"]
    
    cursor = db["tv_series"].find({
        "status": {"$in": non_released_statuses},
        "is_deleted": {"$ne": True}
    })
    
    async for doc in cursor:
        rd_str = doc.get("first_air_date")
        rp = doc.get("first_air_precision")
        
        if rd_str:
            if rd_str <= today_str:
                await db["tv_series"].update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"status": "Returning Series", "needs_release_review": False}} 
                )
                auto_released += 1
        elif rp:
            precision = rp.get("precision")
            y = rp.get("year")
            m = rp.get("month")
            if precision in ("month", "year") and y:
                window_end = _get_window_end_date(y, m if precision == "month" else None)
                if today > window_end:
                    if not doc.get("needs_release_review"):
                        await db["tv_series"].update_one(
                            {"_id": doc["_id"]},
                            {"$set": {"needs_release_review": True}}
                        )
                        flagged_for_review += 1
                        
    return {"auto_released": auto_released, "flagged_for_review": flagged_for_review}

async def sync_all_release_statuses():
    anime_summary = await sync_anime_release_status()
    movie_summary = await sync_movie_release_status()
    tv_summary = await sync_tv_series_release_status()
    
    return {
        "anime": anime_summary,
        "movies": movie_summary,
        "tv_series": tv_summary,
        "total_auto_released": anime_summary["auto_released"] + movie_summary["auto_released"] + tv_summary["auto_released"],
        "total_flagged": anime_summary["flagged_for_review"] + movie_summary["flagged_for_review"] + tv_summary["flagged_for_review"]
    }
