from datetime import datetime
from app.db.mongo import get_db

import calendar

async def get_dated_releases_range(start_date: str, end_date: str):
    db = get_db()
    results = []

    # 1. Movies (release_start)
    movie_cursor = db["movies"].find(
        {
            "release_date": {"$gte": start_date, "$lte": end_date},
            "is_deleted": {"$ne": True}
        },
        {"_id": 1, "title": 1, "images.poster": 1, "release_date": 1}
    )
    movies = await movie_cursor.to_list(None)
    for m in movies:
        results.append({
            "content_type": "movie",
            "content_id": str(m["_id"]),
            "title": m.get("title", ""),
            "poster_image": m.get("images", {}).get("poster"),
            "date": m.get("release_date"),
            "event_type": "release_start"
        })

    # 2. TV Series (release_start & release_end)
    tv_start_cursor = db["tv_series"].find(
        {
            "first_air_date": {"$gte": start_date, "$lte": end_date},
            "is_deleted": {"$ne": True}
        },
        {"_id": 1, "title": 1, "images.poster": 1, "first_air_date": 1}
    )
    tv_starts = await tv_start_cursor.to_list(None)
    for tv in tv_starts:
        results.append({
            "content_type": "tv_series",
            "content_id": str(tv["_id"]),
            "title": tv.get("title", ""),
            "poster_image": tv.get("images", {}).get("poster"),
            "date": tv.get("first_air_date"),
            "event_type": "release_start"
        })

    tv_end_cursor = db["tv_series"].find(
        {
            "last_air_date": {"$gte": start_date, "$lte": end_date},
            "is_deleted": {"$ne": True}
        },
        {"_id": 1, "title": 1, "images.poster": 1, "last_air_date": 1}
    )
    tv_ends = await tv_end_cursor.to_list(None)
    for tv in tv_ends:
        results.append({
            "content_type": "tv_series",
            "content_id": str(tv["_id"]),
            "title": tv.get("title", ""),
            "poster_image": tv.get("images", {}).get("poster"),
            "date": tv.get("last_air_date"),
            "event_type": "release_end"
        })

    # 3. Anime
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    anime_cursor = db["anime"].find(
        {
            "is_deleted": {"$ne": True},
            "$or": [
                {"release_date.precision": "day", "release_date.year": {"$gte": start_dt.year, "$lte": end_dt.year}},
                {"end_date.precision": "day", "end_date.year": {"$gte": start_dt.year, "$lte": end_dt.year}}
            ]
        },
        {"_id": 1, "title": 1, "images.poster": 1, "release_date": 1, "end_date": 1}
    )
    animes = await anime_cursor.to_list(None)
    for a in animes:
        title_obj = a.get("title", {})
        title_str = title_obj.get("english") or title_obj.get("romaji") or title_obj.get("japanese") or ""
        poster = a.get("images", {}).get("poster")

        rd = a.get("release_date")
        if rd and rd.get("precision") == "day" and rd.get("year") and rd.get("month") and rd.get("day"):
            date_str = f"{rd['year']:04d}-{rd['month']:02d}-{rd['day']:02d}"
            if start_date <= date_str <= end_date:
                results.append({
                    "content_type": "anime",
                    "content_id": str(a["_id"]),
                    "title": title_str,
                    "poster_image": poster,
                    "date": date_str,
                    "event_type": "release_start"
                })

        ed = a.get("end_date")
        if ed and ed.get("precision") == "day" and ed.get("year") and ed.get("month") and ed.get("day"):
            date_str = f"{ed['year']:04d}-{ed['month']:02d}-{ed['day']:02d}"
            if start_date <= date_str <= end_date:
                results.append({
                    "content_type": "anime",
                    "content_id": str(a["_id"]),
                    "title": title_str,
                    "poster_image": poster,
                    "date": date_str,
                    "event_type": "release_end"
                })

    # 4. Episodes and Chapters
    from app.services.content_lookup import resolve_content_title
    
    ep_cursor = db["episodes"].find(
        {
            "release_date": {"$gte": start_date, "$lte": end_date},
            "is_deleted": {"$ne": True}
        }
    )
    episodes = await ep_cursor.to_list(None)
    for ep in episodes:
        parent_type = "anime" if ep.get("anime_id") else "tv_series"
        parent_id = ep.get("anime_id") or ep.get("tv_series_id")
        doc_info = await resolve_content_title(parent_type, parent_id)
        if doc_info:
            ep_num = ep.get("episode_number")
            ep_title = ep.get("title")
            name_label = f"Episode {ep_num}: {ep_title}" if ep_title else f"Episode {ep_num}"
            results.append({
                "content_type": "episode",
                "content_id": str(ep["_id"]),
                "parent_title": doc_info["title"],
                "parent_id": parent_id,
                "title": name_label,
                "poster_image": doc_info["poster_image"],
                "date": ep.get("release_date"),
                "event_type": "episode_release",
                "summary": ep.get("summary")
            })

    ch_cursor = db["chapters"].find(
        {
            "release_date": {"$gte": start_date, "$lte": end_date},
            "is_deleted": {"$ne": True}
        }
    )
    chapters = await ch_cursor.to_list(None)
    for ch in chapters:
        doc_info = await resolve_content_title("manga", ch.get("manga_id"))
        if doc_info:
            ch_num = ch.get("chapter_number")
            results.append({
                "content_type": "chapter",
                "content_id": str(ch["_id"]),
                "parent_title": doc_info["title"],
                "parent_id": ch.get("manga_id"),
                "title": f"Chapter {ch_num}",
                "poster_image": doc_info["poster_image"],
                "date": ch.get("release_date"),
                "event_type": "chapter_release",
                "summary": ch.get("summary")
            })

    results.sort(key=lambda x: x["date"])
    return results


import random
from datetime import timezone

async def get_weekly_suggestions(picks_per_type: int = 2):
    db = get_db()
    from app.repositories.rating_repository import get_top_rated
    
    now = datetime.now(timezone.utc)
    iso_year, iso_week, _ = now.isocalendar()
    weekly_seed = f"{iso_year}-W{iso_week}"
    
    rng = random.Random(weekly_seed)
    
    content_types = ["anime", "manga", "movie", "tv_series"]
    results = []
    
    for c_type in content_types:
        # Get top rated items to build a qualified pool
        top_rated = await get_top_rated(content_type=c_type, limit=50)
        
        # Filter for count >= 3
        qualified_pool = [item for item in top_rated if item.get("count", 0) >= 3]
        
        reason = ""
        
        if len(qualified_pool) >= picks_per_type:
            # We have enough rated items
            reason = "Highly rated"
            content_ids = [item["_id"]["content_id"] for item in qualified_pool]
        else:
            # Fallback to recent/all non-deleted items
            reason = "Recently added"
            fallback_cursor = db[c_type].find(
                {"is_deleted": {"$ne": True}},
                {"_id": 1}
            ).sort("_id", -1).limit(50)
            fallback_items = await fallback_cursor.to_list(None)
            content_ids = [str(item["_id"]) for item in fallback_items]
        
        # Sample picks_per_type if pool is large enough, else take all
        k = min(picks_per_type, len(content_ids))
        if k == 0:
            continue
            
        picked_ids = rng.sample(content_ids, k)
        
        # Fetch the details for picked_ids
        docs = await db[c_type].find(
            {"_id": {"$in": picked_ids}},
            {"_id": 1, "title": 1, "images.poster": 1, "name": 1, "cover_image": 1, "poster": 1}
        ).to_list(None)
        
        # Map documents back to maintain consistent format
        for doc in docs:
            title_obj = doc.get("title") or doc.get("name") or {}
            if isinstance(title_obj, dict):
                title_str = title_obj.get("english") or title_obj.get("romaji") or title_obj.get("japanese") or ""
            else:
                title_str = title_obj
                
            poster_image = doc.get("images", {}).get("poster") or doc.get("cover_image") or doc.get("poster")
                
            results.append({
                "content_type": c_type,
                "content_id": str(doc["_id"]),
                "title": title_str,
                "poster_image": poster_image,
                "reason": reason
            })
            
    return results


async def get_announced_releases_range(start_date: str, end_date: str):
    db = get_db()
    results = []

    def process_precision_date(doc, date_obj, event_type, content_type, title_str):
        if not date_obj or date_obj.get("precision") not in ("month", "year"):
            return

        y = date_obj.get("year")
        precision = date_obj.get("precision")
        if not y:
            return

        if precision == "month":
            m = date_obj.get("month", 12)
            _, last_day = calendar.monthrange(y, m)
            pinned_date = f"{y:04d}-{m:02d}-{last_day:02d}"
            label = datetime(y, m, 1).strftime("%B %Y")
        else:
            pinned_date = f"{y:04d}-12-31"
            label = str(y)

        if start_date <= pinned_date <= end_date:
            results.append({
                "content_type": content_type,
                "content_id": str(doc["_id"]),
                "title": title_str,
                "poster_image": doc.get("images", {}).get("poster"),
                "pinned_date": pinned_date,
                "label": label,
                "event_type": event_type
            })

    # 1. Movies (release_precision)
    movie_cursor = db["movies"].find(
        {
            "release_precision": {"$exists": True, "$ne": None},
            "is_deleted": {"$ne": True}
        },
        {"_id": 1, "title": 1, "images.poster": 1, "release_precision": 1}
    )
    movies = await movie_cursor.to_list(None)
    for m in movies:
        process_precision_date(m, m.get("release_precision"), "announced_start", "movie", m.get("title", ""))

    # 2. TV Series (first_air_precision and last_air_precision)
    tv_cursor = db["tv_series"].find(
        {
            "$or": [
                {"first_air_precision": {"$exists": True, "$ne": None}},
                {"last_air_precision": {"$exists": True, "$ne": None}}
            ],
            "is_deleted": {"$ne": True}
        },
        {"_id": 1, "title": 1, "images.poster": 1, "first_air_precision": 1, "last_air_precision": 1}
    )
    tvs = await tv_cursor.to_list(None)
    for tv in tvs:
        process_precision_date(tv, tv.get("first_air_precision"), "announced_start", "tv_series", tv.get("title", ""))
        process_precision_date(tv, tv.get("last_air_precision"), "announced_end", "tv_series", tv.get("title", ""))

    # 3. Anime (release_date and end_date)
    anime_cursor = db["anime"].find(
        {
            "$or": [
                {"release_date.precision": {"$in": ["month", "year"]}},
                {"end_date.precision": {"$in": ["month", "year"]}}
            ],
            "is_deleted": {"$ne": True}
        },
        {"_id": 1, "title": 1, "images.poster": 1, "release_date": 1, "end_date": 1}
    )
    animes = await anime_cursor.to_list(None)
    for a in animes:
        title_obj = a.get("title", {})
        title_str = title_obj.get("english") or title_obj.get("romaji") or title_obj.get("japanese") or ""
        process_precision_date(a, a.get("release_date"), "announced_start", "anime", title_str)
        process_precision_date(a, a.get("end_date"), "announced_end", "anime", title_str)

    results.sort(key=lambda x: x["pinned_date"])
    return results

