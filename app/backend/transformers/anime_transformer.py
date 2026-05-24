from app.backend.utils.slug import create_slug
from app.backend.constants.anime_enums import (
    STATUS_MAPPING,
    TYPE_MAPPING,
    SOURCE_MAPPING
)


def transform_anime(anime):

    title = (
        anime["title"].get("english")
        or anime["title"].get("romaji")
        or anime["title"].get("native")
    )

    slug = create_slug(title)

    return {
        "_id": f"anime_{slug}",

        "title": {
            "english": anime["title"].get("english"),
            "japanese": anime["title"].get("native"),
            "romaji": anime["title"].get("romaji")
        },

        "synonyms": anime.get("synonyms", []),

        "type": TYPE_MAPPING.get(anime.get("format"),"unknown"),

        "status": STATUS_MAPPING.get(anime.get("status", ""),"unknown"),

        "genres": anime.get("genres", []),

        "studios": [
            studio["name"]
            for studio in anime.get("studios", {}).get("nodes", [])
        ],

        "season": anime.get("season", "").title(),

        "year": anime.get("seasonYear"),

        "source": SOURCE_MAPPING.get(anime.get("source", ""),"unknown"),

        "total_seasons": 1,

        "total_episodes": anime.get("episodes"),

        "duration_minutes": anime.get("duration"),

        "rating": {
            "anilist": anime.get("averageScore")
        },

        "images": {
            "poster": anime.get("coverImage", {}).get("large"),
            "banner": anime.get("bannerImage")
        },

        "streaming_platforms": [],

        "related_anime_ids": [],

        "manga_id": None,

        "tags": [],

        "source_metadata": {
            "anilist_id": anime["id"]
        },

        "is_deleted": False,

        "deleted_at": None
    }