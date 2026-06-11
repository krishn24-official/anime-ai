from app.repositories.home_repository import (
    get_today_birthdays,
    get_today_anime_anniversaries,
    get_today_manga_anniversaries
)


async def fetch_home_today():

    birthdays = await (
        get_today_birthdays()
    )

    anime_anniversaries = await (
        get_today_anime_anniversaries()
    )

    manga_anniversaries = await (
        get_today_manga_anniversaries()
    )

    return {

        "birthdays":
            birthdays,

        "anime_anniversaries":
            anime_anniversaries,

        "manga_anniversaries":
            manga_anniversaries,

        "special_events": []
    }