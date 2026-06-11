from app.backend.utils.slug import create_slug
from app.backend.transformers.character_transformer import (
    clean_description
)


def format_date(date_data):

    if (
        not date_data
        or not date_data.get("year")
    ):
        return None

    return (
        f"{date_data.get('year')}-"
        f"{date_data.get('month')}-"
        f"{date_data.get('day')}"
    )


def extract_author(manga):

    staff_edges = (
        manga.get("staff", {})
        .get("edges", [])
    )

    for edge in staff_edges:

        role = (
            edge.get("role", "")
            .lower()
        )

        if (
            "story" in role
            or "original creator" in role
            or "creator" in role
        ):

            return (
                edge["node"]["name"]["full"]
            )

    return None


def transform_manga(manga):

    title = (
        manga["title"].get("english")
        or manga["title"].get("romaji")
    )

    slug = create_slug(title)

    return {

        "_id": f"manga_{slug}",

        "name": title,

        "native_name": (
            manga["title"].get("native")
        ),

        "description": clean_description(
            manga.get("description")
        ),

        "author": extract_author(
            manga
        ),

        "total_chapters": (
            manga.get("chapters")
        ),

        "total_volumes": (
            manga.get("volumes")
        ),

        "start_date": format_date(
            manga.get("startDate")
        ),

        "end_date": format_date(
            manga.get("endDate")
        ),

        "status": (
            manga.get("status", "")
            .lower()
        ),

        "genres": (
            manga.get("genres", [])
        ),

        "serialization": None,

        "cover_image": (
            manga.get("coverImage", {})
            .get("large")
        ),

        "banner_image": (
            manga.get("bannerImage")
        ),

        "related_anime_ids": [],

        "source_metadata": {
            "anilist": {
                "id": manga["id"]
            }
        },

        "tags": [],

        "is_deleted": False,

        "deleted_at": None
    }