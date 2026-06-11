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

        if years_ago is not None:

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

        if years_ago is not None:

            manga["years_ago"] = (
                years_ago
            )

            result.append(
                manga
            )

    return result