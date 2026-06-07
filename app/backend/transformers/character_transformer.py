import re

from app.backend.utils.slug import create_slug


def clean_description(text):

    if not text:
        return None

    # Remove image markdown
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)

    # Remove markdown bold/underline markers
    text = re.sub(r'__([^_]*)__', r'\1', text)

    # Remove spoiler markers
    text = re.sub(r'~!.*?!~', '', text)

    # Remove HTML tags
    text = re.sub(r'<.*?>', '', text)

    # Replace <br> with space
    text = re.sub(r'<br\s*/?>', ' ', text)

    # Remove multiple spaces/newlines
    text = re.sub(r'\s+', ' ', text)

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

        # IMPORTANT:
        # this will later be merged in ingestion
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

        "role": (
            role.lower()
            if role
            else "unknown"
        ),

        "tags": [],

        "source_metadata": {
            "anilist": {
                "id": character["id"]
            }
        },

        "is_deleted": False,

        "deleted_at": None
    }