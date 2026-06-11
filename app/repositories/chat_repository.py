from app.repositories.search_repository import (
    search_characters
)


async def find_character(
    query: str
):

    results = await (
        search_characters(
            query
        )
    )

    if not results:
        return None

    return results[0]