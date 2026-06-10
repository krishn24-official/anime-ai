from app.repositories.character_repository import (
    get_all_characters,
    get_character_by_id,
    search_characters,
    get_character_basic
)

from app.repositories.relationship_repository import (
    get_relationships_by_type
)


async def fetch_all_characters():

    return await get_all_characters()


async def fetch_character(
    character_id: str
):

    return await get_character_by_id(
        character_id
    )


async def search_character(
    query: str
):

    return await search_characters(
        query
    )


async def enrich_relationships(
    relationships
):

    enriched = []

    for relationship in relationships:

        target = await get_character_basic(
            relationship["target_id"]
        )

        enriched.append(
            {
                "relationship":
                    relationship["relationship"],

                "type":
                    relationship["type"],

                "target":
                    target
            }
        )

    return enriched


async def fetch_character_details(
    character_id: str
):

    character = await get_character_by_id(
        character_id
    )

    if not character:
        return None

    family = await get_relationships_by_type(
        character_id,
        "family"
    )

    friends = await get_relationships_by_type(
        character_id,
        "friendship"
    )

    team = await get_relationships_by_type(
        character_id,
        "team"
    )

    mentors = await get_relationships_by_type(
        character_id,
        "mentor"
    )

    combat = await get_relationships_by_type(
        character_id,
        "combat"
    )

    family = await enrich_relationships(
        family
    )

    friends = await enrich_relationships(
        friends
    )

    team = await enrich_relationships(
        team
    )

    mentors = await enrich_relationships(
        mentors
    )

    combat = await enrich_relationships(
        combat
    )

    return {
        "character": character,
        "family": family,
        "friends": friends,
        "team": team,
        "mentors": mentors,
        "combat": combat
    }

async def fetch_character_summary(
    character_id: str
):

    character = await get_character_by_id(
        character_id
    )

    if not character:
        return None

    family = await get_relationships_by_type(
        character_id,
        "family"
    )

    friends = await get_relationships_by_type(
        character_id,
        "friendship"
    )

    team = await get_relationships_by_type(
        character_id,
        "team"
    )

    mentors = await get_relationships_by_type(
        character_id,
        "mentor"
    )

    combat = await get_relationships_by_type(
        character_id,
        "combat"
    )

    return {

        "_id": character["_id"],

        "name": character["name"],

        "native_name": character.get(
            "native_name"
        ),

        "image": (
            character.get(
                "images",
                {}
            ).get(
                "profile"
            )
        ),

        "role": character.get(
            "role"
        ),

        "gender": character.get(
            "gender"
        ),

        "anime_count": len(
            character.get(
                "anime_ids",
                []
            )
        ),

        "family_count": len(
            family
        ),

        "friend_count": len(
            friends
        ),

        "team_count": len(
            team
        ),

        "mentor_count": len(
            mentors
        ),

        "combat_count": len(
            combat
        )
    }