from app.backend.ingestion.tmdb_client import image_url
from app.backend.utils.slug import create_slug


def _extract_trailer(videos: dict | None) -> str | None:
    if not videos:
        return None

    results = videos.get("results", [])

    for video in results:
        if video.get("site") == "YouTube" and video.get("type") == "Trailer":
            return f"https://www.youtube.com/watch?v={video['key']}"

    # fallback: any YouTube video
    for video in results:
        if video.get("site") == "YouTube":
            return f"https://www.youtube.com/watch?v={video['key']}"

    return None


def _extract_cast(credits: dict | None, limit: int = 10) -> list[dict]:
    if not credits:
        return []

    cast = credits.get("cast", [])[:limit]

    return [
        {
            "name": person.get("name"),
            "character": person.get("character"),
            "profile_image": image_url(person.get("profile_path"), "w185"),
        }
        for person in cast
    ]


def _extract_directors(credits: dict | None) -> list[str]:
    """Pull director names from the crew list."""
    if not credits:
        return []
    return [
        person["name"]
        for person in credits.get("crew", [])
        if person.get("job") == "Director"
    ]


def _extract_writers(credits: dict | None) -> list[str]:
    """Pull writer names from the crew list."""
    if not credits:
        return []
    return [
        person["name"]
        for person in credits.get("crew", [])
        if person.get("department") == "Writing"
    ]


def map_movie(details: dict) -> dict:
    tmdb_id = details["id"]
    title = details.get("title") or details.get("original_title") or str(tmdb_id)
    slug = create_slug(title)

    return {
        "_id": f"movie_{slug}",

        "title": title,
        "original_title": details.get("original_title"),

        "year": (details.get("release_date") or "")[:4] or None,
        "release_date": details.get("release_date"),

        "runtime_minutes": details.get("runtime"),

        "genres": [g["name"] for g in details.get("genres", [])],

        "director": _extract_directors(details.get("credits")),
        "writers": _extract_writers(details.get("credits")),
        "cast": _extract_cast(details.get("credits")),

        "plot": details.get("overview"),

        "language": [
            lang.get("english_name") or lang.get("name")
            for lang in details.get("spoken_languages", [])
        ],

        "country": [
            c.get("name")
            for c in details.get("production_countries", [])
        ],

        "rating": {
            "tmdb": details.get("vote_average"),
            "tmdb_vote_count": details.get("vote_count"),
        },

        "images": {
            "poster": image_url(details.get("poster_path")),
            "backdrop": image_url(details.get("backdrop_path"), "w1280"),
        },

        "trailer_url": _extract_trailer(details.get("videos")),
        "status": details.get("status"),
        "tagline": details.get("tagline"),
        "budget": details.get("budget"),
        "revenue": details.get("revenue"),

        "content_type": "movie",

        "source_metadata": {
            "tmdb_id": tmdb_id,
            "imdb_id": details.get("imdb_id"),
        },

        "is_deleted": False,
        "deleted_at": None,
    }


def map_tv_series(details: dict) -> dict:
    tmdb_id = details["id"]
    title = details.get("name") or details.get("original_name") or str(tmdb_id)
    slug = create_slug(title)

    return {
        "_id": f"tv_{slug}",

        "title": title,
        "original_title": details.get("original_name"),

        "year": (details.get("first_air_date") or "")[:4] or None,
        "first_air_date": details.get("first_air_date"),
        "last_air_date": details.get("last_air_date"),

        "total_seasons": details.get("number_of_seasons"),
        "total_episodes": details.get("number_of_episodes"),
        "episode_runtime_minutes": (details.get("episode_run_time") or [None])[0],

        "genres": [g["name"] for g in details.get("genres", [])],

        "creators": [c["name"] for c in details.get("created_by", [])],
        "cast": _extract_cast(details.get("credits")),

        "plot": details.get("overview"),

        "language": [
            lang.get("english_name") or lang.get("name")
            for lang in details.get("spoken_languages", [])
        ],

        "country": [
            c.get("name")
            for c in details.get("production_countries", [])
        ],

        "rating": {
            "tmdb": details.get("vote_average"),
            "tmdb_vote_count": details.get("vote_count"),
        },

        "images": {
            "poster": image_url(details.get("poster_path")),
            "backdrop": image_url(details.get("backdrop_path"), "w1280"),
        },

        "trailer_url": _extract_trailer(details.get("videos")),
        "status": details.get("status"),
        "tagline": details.get("tagline"),

        "content_type": "tv_series",

        "source_metadata": {
            "tmdb_id": tmdb_id,
        },

        "is_deleted": False,
        "deleted_at": None,
    }