from app.repositories.anime_repository import (
    get_all_anime,
    get_anime_by_id,
    search_anime,
    get_anime_characters,
    get_character_count
)


async def fetch_all_anime():

    return await get_all_anime()


async def fetch_anime(
    anime_id: str
):

    return await get_anime_by_id(
        anime_id
    )


async def fetch_anime_search(
    query: str
):

    return await search_anime(
        query
    )

async def fetch_anime_characters(
    anime_id: str
):

    return await get_anime_characters(
        anime_id
    )

async def fetch_anime_details(
    anime_id: str
):

    anime = await get_anime_by_id(
        anime_id
    )

    if not anime:
        return None

    character_count = await (
        get_character_count(
            anime_id
        )
    )


    return {
        "anime": anime,
        "character_count": character_count
    }

async def fetch_anime_summary(
    anime_id: str
):

    anime = await get_anime_by_id(
        anime_id
    )

    if not anime:
        return None

    character_count = await (
        get_character_count(
            anime_id
        )
    )

    return {

        "_id": anime["_id"],

        "title": anime.get(
            "title"
        ),

        "image": (
            anime.get(
                "images",
                {}
            ).get(
                "poster"
            )
        ),

        "type": anime.get(
            "type"
        ),

        "status": anime.get(
            "status"
        ),

        "year": anime.get(
            "year"
        ),

        "season": anime.get(
            "season"
        ),

        "genres": anime.get(
            "genres",
            []
        ),

        "character_count":
            character_count
    }