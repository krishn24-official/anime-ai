from datetime import datetime

from app.db.mongo import get_db


def get_years_ago(
    start_date: str
):

    if not start_date:
        return None

    try:

        year, month, day = map(
            int,
            start_date.split("-")
        )

        today = datetime.utcnow()

        if (
            month == today.month
            and day == today.day
        ):

            return (
                today.year - year
            )

    except Exception:

        return None

    return None


async def get_today_birthdays():

    db = get_db()

    today = datetime.utcnow()

    return await (
        db["characters"]
        .find(
            {
                "birth_month": today.month,
                "birth_day": today.day,
                "is_deleted": False
            },
            {
                "_id": 1,
                "name": 1,
                "images.profile": 1,
                "role": 1
            }
        )
        .to_list(None)
    )


async def get_today_actor_birthdays():
    db = get_db()
    today = datetime.utcnow()
    
    # Standard TMDB format
    regex_pattern = f"-{today.month:02d}-{today.day:02d}$"
    # Manual entry format
    month_name = today.strftime("%B")
    manual_regex_pattern = f"^{month_name} {today.day},"

    return await (
        db["actors"]
        .find(
            {
                "$or": [
                    {"birthdate": {"$regex": regex_pattern}},
                    {"birthdate": {"$regex": manual_regex_pattern}}
                ],
                "is_deleted": False
            },
            {
                "_id": 1,
                "name": 1,
                "images.profile": 1,
                "role": 1
            }
        )
        .to_list(None)
    )


async def get_today_anime_anniversaries():

    db = get_db()

    anime_list = await (
        db["anime"]
        .find(
            {
                "is_deleted": False
            }
        )
        .to_list(None)
    )

    result = []

    for anime in anime_list:

        years_ago = get_years_ago(
            anime.get("start_date")
        )

        if years_ago is not None and years_ago > 0:

            anime["years_ago"] = (
                years_ago
            )

            result.append(
                anime
            )

    return result


async def get_today_manga_anniversaries():

    db = get_db()

    manga_list = await (
        db["manga"]
        .find(
            {
                "is_deleted": False
            }
        )
        .to_list(None)
    )

    result = []

    for manga in manga_list:

        years_ago = get_years_ago(
            manga.get("start_date")
        )

        if years_ago is not None and years_ago > 0:

            manga["years_ago"] = (
                years_ago
            )

            result.append(
                manga
            )

    return result


async def get_today_movie_anniversaries():

    db = get_db()

    movie_list = await (
        db["movies"]
        .find(
            {
                "is_deleted": False
            }
        )
        .to_list(None)
    )

    result = []

    for movie in movie_list:

        years_ago = get_years_ago(
            movie.get("release_date")
        )

        if years_ago is not None and years_ago > 0:

            movie["years_ago"] = (
                years_ago
            )

            result.append(
                movie
            )

    return result


async def get_today_tv_series_anniversaries():

    db = get_db()

    tv_list = await (
        db["tv_series"]
        .find(
            {
                "is_deleted": False
            }
        )
        .to_list(None)
    )

    result = []

    for tv in tv_list:

        years_ago = get_years_ago(
            tv.get("first_air_date")
        )

        if years_ago is not None and years_ago > 0:

            tv["years_ago"] = (
                years_ago
            )

            result.append(
                tv
            )

    return result


async def get_today_episode_anniversaries():
    """Episodes released on this calendar date in previous years."""
    from app.services.content_lookup import resolve_content_title
    
    db = get_db()
    today = datetime.utcnow()
    current_year = today.year
    
    # Match episodes whose release_date ends with today's MM-DD
    regex_pattern = f"-{today.month:02d}-{today.day:02d}$"
    
    episodes = await (
        db["episodes"]
        .find({
            "release_date": {"$regex": regex_pattern},
            "is_deleted": {"$ne": True}
        })
        .to_list(None)
    )
    
    result = []
    for ep in episodes:
        years_ago = get_years_ago(ep.get("release_date"))
        if years_ago is None or years_ago == 0:
            continue  # Skip current year (belongs in Today's Releases)
        
        parent_type = "anime" if ep.get("anime_id") else "tv_series"
        parent_id = ep.get("anime_id") or ep.get("tv_series_id")
        doc_info = await resolve_content_title(parent_type, parent_id) if parent_id else None
        
        ep_num = ep.get("episode_number")
        ep_title = ep.get("title")
        name_label = f"Episode {ep_num}: {ep_title}" if ep_title else f"Episode {ep_num}"
        
        result.append({
            "content_id": str(ep["_id"]),
            "content_type": "episode",
            "title": name_label,
            "parent_type": parent_type,
            "parent_id": parent_id,
            "parent_title": doc_info["title"] if doc_info else None,
            "poster_image": doc_info["poster_image"] if doc_info else None,
            "release_date": ep.get("release_date"),
            "years_ago": years_ago,
            "summary": ep.get("summary"),
        })
    
    return result


async def get_today_chapter_anniversaries():
    """Chapters released on this calendar date in previous years."""
    from app.services.content_lookup import resolve_content_title
    
    db = get_db()
    today = datetime.utcnow()
    
    regex_pattern = f"-{today.month:02d}-{today.day:02d}$"
    
    chapters = await (
        db["chapters"]
        .find({
            "release_date": {"$regex": regex_pattern},
            "is_deleted": {"$ne": True}
        })
        .to_list(None)
    )
    
    result = []
    for ch in chapters:
        years_ago = get_years_ago(ch.get("release_date"))
        if years_ago is None or years_ago == 0:
            continue
        
        manga_id = ch.get("manga_id")
        doc_info = await resolve_content_title("manga", manga_id) if manga_id else None
        
        ch_num = ch.get("chapter_number")
        
        result.append({
            "content_id": str(ch["_id"]),
            "content_type": "chapter",
            "title": f"Chapter {ch_num}",
            "parent_id": manga_id,
            "parent_title": doc_info["title"] if doc_info else None,
            "poster_image": doc_info["poster_image"] if doc_info else None,
            "release_date": ch.get("release_date"),
            "years_ago": years_ago,
            "summary": ch.get("summary"),
        })
    
    return result