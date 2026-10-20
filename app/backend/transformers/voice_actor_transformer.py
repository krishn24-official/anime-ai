from app.backend.utils.slug import create_slug
from app.backend.transformers.character_transformer import clean_description


def transform_voice_actor(staff):
    name = staff.get("name", {}).get("full")
    slug = create_slug(name)

    return {
        "_id": f"va_{slug}",
        "name": name,
        "native_name": staff.get("name", {}).get("native"),
        "birth_year": (staff.get("dateOfBirth") or {}).get("year"),
        "birth_month": (staff.get("dateOfBirth") or {}).get("month"),
        "birth_day": (staff.get("dateOfBirth") or {}).get("day"),
        "image": staff.get("image", {}).get("large"),
        "description": clean_description(staff.get("description")),
        "gender": staff.get("gender", "").lower() if staff.get("gender") else None,
        "is_deleted": False,
        "deleted_at": None,
        "source_metadata": {"anilist": {"id": staff.get("id")}},
    }
