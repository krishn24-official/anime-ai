from app.repositories.character_repository import (
    get_all_characters,
    get_character_by_id,
    search_characters,
    get_character_basic,
    get_birthdays_by_date_range
)

from app.repositories.relationship_repository import (
    get_relationships_by_type
)

from app.repositories.organization_repository import (
    find_organizations_by_names
)

from app.repositories.anime_repository import find_anime_by_ids


async def fetch_all_characters(skip: int = 0, limit: int = 50):
    return await get_all_characters(skip=skip, limit=limit)


async def fetch_birthdays_by_date_range(start_date: str, end_date: str):
    return await get_birthdays_by_date_range(start_date, end_date)


async def fetch_character(
    character_id: str
):
    character = await get_character_by_id(character_id)
    if not character:
        return None
        
    anime_ids = character.get("anime_ids", [])
    anime_details = []
    if anime_ids:
        animes = await find_anime_by_ids(anime_ids)
        for a in animes:
            title = a.get("title", {})
            title_str = title.get("english") or title.get("romaji", "")
            anime_details.append({
                "id": a["_id"],
                "title": title_str,
                "poster": a.get("images", {}).get("poster", ""),
                "year": a.get("year", "")
            })
    character["anime_details"] = anime_details
    return character

async def search_character(
    query: str
):

    return await search_characters(
        query
    )


async def enrich_relationships_by_source(
    relationships
):

    enriched = []

    for relationship in relationships:

        source = await get_character_basic(
            relationship["source_id"]
        )

        enriched.append(
            {
                "relationship":
                    relationship["relationship"],

                "type":
                    relationship["type"],

                "target":
                    source
            }
        )

    return enriched


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


def deduplicate_by_target(relationships):
    seen = set()
    unique = []
    for r in relationships:
        target_id = r.get("target_id")
        if target_id not in seen:
            seen.add(target_id)
            unique.append(r)
    return unique


async def fetch_character_details(
    character_id: str
):

    character = await get_character_by_id(
        character_id
    )

    if not character:
        return None

    family = deduplicate_by_target(await get_relationships_by_type(
        character_id,
        "family"
    ))

    friends = deduplicate_by_target(await get_relationships_by_type(
        character_id,
        "friendship"
    ))

    team = deduplicate_by_target(await get_relationships_by_type(
        character_id,
        "team"
    ))

    mentors = deduplicate_by_target(await get_relationships_by_type(
        character_id,
        "mentor"
    ))

    combat = deduplicate_by_target(await get_relationships_by_type(
        character_id,
        "combat"
    ))

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

    affiliations = character.get("affiliations", [])
    organizations = []
    if affiliations:
        org_docs = await find_organizations_by_names(affiliations)
        organizations = [
            {
                "id": str(org["_id"]),
                "name": org.get("name"),
                "type": org.get("type"),
                "images": org.get("images", {"logo": "", "banner": ""}),
                "status": org.get("status")
            }
            for org in org_docs
        ]

    return {
        "character": character,
        "family": family,
        "friends": friends,
        "team": team,
        "mentors": mentors,
        "combat": combat,
        "organizations": organizations
    }

async def fetch_character_summary(
    character_id: str
):

    character = await get_character_by_id(
        character_id
    )

    if not character:
        return None

    family = deduplicate_by_target(await get_relationships_by_type(
        character_id,
        "family"
    ))

    friends = deduplicate_by_target(await get_relationships_by_type(
        character_id,
        "friendship"
    ))

    team = deduplicate_by_target(await get_relationships_by_type(
        character_id,
        "team"
    ))

    mentors = deduplicate_by_target(await get_relationships_by_type(
        character_id,
        "mentor"
    ))

    combat = deduplicate_by_target(await get_relationships_by_type(
        character_id,
        "combat"
    ))

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