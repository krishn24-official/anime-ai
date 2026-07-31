from app.repositories.home_repository import (
    get_today_birthdays,
    get_today_actor_birthdays,
    get_today_anime_anniversaries,
    get_today_manga_anniversaries,
    get_today_episode_anniversaries,
    get_today_chapter_anniversaries,
    get_today_movie_anniversaries,
    get_today_tv_series_anniversaries
)

from app.services.news_service import fetch_latest_news


async def fetch_home_today():

    birthdays = await (
        get_today_birthdays()
    )
    
    actor_birthdays = await (
        get_today_actor_birthdays()
    )
    
    for ab in actor_birthdays:
        ab["entity_type"] = "actor"
        
    for b in birthdays:
        b["entity_type"] = "character"
        
    all_birthdays = birthdays + actor_birthdays

    anime_anniversaries = await (
        get_today_anime_anniversaries()
    )

    manga_anniversaries = await (
        get_today_manga_anniversaries()
    )

    episode_anniversaries = await (
        get_today_episode_anniversaries()
    )

    chapter_anniversaries = await (
        get_today_chapter_anniversaries()
    )

    movie_anniversaries = await (
        get_today_movie_anniversaries()
    )

    tv_series_anniversaries = await (
        get_today_tv_series_anniversaries()
    )

    latest_news = await (
        fetch_latest_news(limit=5)
    )

    return {

        "birthdays":
            all_birthdays,

        "anime_anniversaries":
            anime_anniversaries,

        "manga_anniversaries":
            manga_anniversaries,

        "episode_anniversaries":
            episode_anniversaries,

        "chapter_anniversaries":
            chapter_anniversaries,

        "movie_anniversaries":
            movie_anniversaries,

        "tv_series_anniversaries":
            tv_series_anniversaries,

        "special_events": [],

        "latest_news":
            latest_news
    }