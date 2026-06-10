from app.repositories.relationship_repository import (
    get_relationships_by_source,
    get_relationships_by_type
)


async def fetch_relationships(
    character_id: str
):

    return await (
        get_relationships_by_source(
            character_id
        )
    )


async def fetch_family(
    character_id: str
):

    return await (
        get_relationships_by_type(
            character_id,
            "family"
        )
    )


async def fetch_friends(
    character_id: str
):

    return await (
        get_relationships_by_type(
            character_id,
            "friendship"
        )
    )


async def fetch_team(
    character_id: str
):

    return await (
        get_relationships_by_type(
            character_id,
            "team"
        )
    )


async def fetch_mentors(
    character_id: str
):

    return await (
        get_relationships_by_type(
            character_id,
            "mentor"
        )
    )