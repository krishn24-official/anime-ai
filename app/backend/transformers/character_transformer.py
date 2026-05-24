import re

from app.backend.utils.slug import create_slug


def clean_description(text):

    if not text:
        return None

    # Remove AniList markdown formatting
    text = re.sub(r"__.*?__:", "", text)

    # Remove HTML breaks
    text = re.sub(r"<br>", " ", text)

    # Remove extra spaces/newlines
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def transform_character(character, anime_id, role):

    name = character["name"]["full"]

    slug = create_slug(name)

    description = clean_description(
        character.get("description")
    )

    return {

        "_id": f"char_{slug}",

        "name": name,

        "native_name": character["name"].get("native"),

        "birth_day": (
            character.get("dateOfBirth", {})
            .get("day")
        ),

        "birth_month": (
            character.get("dateOfBirth", {})
            .get("month")
        ),

        "physical": {
            "height": None,
            "hair_color": None,
            "has_hair": None
        },

        "description": description,

        "images": {
            "profile": (
                character.get("image", {})
                .get("large")
            ),
            "banner": None
        },

        "anime_ids": [anime_id],

        "manga_ids": [],

        "voice_actor_ids": [],

        "affiliations": [],

        "abilities": [],

        "forms": [],

        "status": "unknown",

        "species": "unknown",

        "gender": (
            character.get("gender", "").lower()
            if character.get("gender")
            else None
        ),

        "role": role.lower() if role else "unknown",

        "tags": [],

        "source_metadata": {
            "anilist_id": character["id"]
        },

        "is_deleted": False,

        "deleted_at": None
    }