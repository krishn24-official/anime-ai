from app.repositories.search_repository import (
    search_characters,
    search_anime,
    search_manga
)


async def global_search(
    query: str
):

    characters = await (
        search_characters(query)
    )

    anime = await (
        search_anime(query)
    )

    manga = await (
        search_manga(query)
    )

    return {

        "characters":
            characters,

        "anime":
            anime,

        "manga":
            manga
    }