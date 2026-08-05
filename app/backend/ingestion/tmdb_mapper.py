from app.backend.ingestion.tmdb_client import image_url
from app.backend.utils.slug import create_slug


def _extract_trailers(videos: dict | None) -> list[dict]:
    if not videos:
        return []

    results = videos.get("results", [])
    trailers = []

    for video in results:
        if video.get("site") == "YouTube":
            label = video.get("type") or "Trailer"
            trailers.append({
                "url": f"https://www.youtube.com/watch?v={video['key']}",
                "label": label
            })

    return trailers


def _extract_cast(credits: dict | None, limit: int = 10) -> list[dict]:
    if not credits:
        return []

    cast = credits.get("cast", [])[:limit]

    return [
        {
            "tmdb_person_id": person.get("id"),
            "name": person.get("name"),
            "character": person.get("character"),
            "profile_image": image_url(person.get("profile_path"), "w185"),
        }
        for person in cast
    ]


def _extract_directors(credits: dict | None) -> list[dict]:
    """Pull director names and info from the crew list."""
    if not credits:
        return []
    
    return [
        {
            "tmdb_person_id": person.get("id"),
            "name": person.get("name"),
            "profile_image": image_url(person.get("profile_path"), "w185"),
        }
        for person in credits.get("crew", [])
        if person.get("job") == "Director"
    ]


def _extract_creators(details: dict) -> list[dict]:
    """Pull creator names and info from the created_by list."""
    return [
        {
            "tmdb_person_id": person.get("id"),
            "name": person.get("name"),
            "profile_image": image_url(person.get("profile_path"), "w185"),
        }
        for person in details.get("created_by", [])
    ]


def _extract_writers(credits: dict | None) -> list[dict]:
    """Pull writer names and info from the crew list."""
    if not credits:
        return []
    
    return [
        {
            "tmdb_person_id": person.get("id"),
            "name": person.get("name"),
            "profile_image": image_url(person.get("profile_path"), "w185"),
        }
        for person in credits.get("crew", [])
        if person.get("department") == "Writing"
    ]


def _extract_us_theatrical_release_date(details: dict) -> str | None:
    """Pull the actual US theatrical release date if available, fallback to top-level."""
    release_dates = details.get("release_dates", {}).get("results", [])
    
    us_data = next((r for r in release_dates if r.get("iso_3166_1") == "US"), None)
    if us_data:
        # Prefer Type 3 (Theatrical), then Type 2 (Theatrical Limited), then Type 1 (Premiere)
        types_to_check = [3, 2, 1]
        for t in types_to_check:
            for rd in us_data.get("release_dates", []):
                if rd.get("type") == t and rd.get("release_date"):
                    return rd.get("release_date")[:10]
                    
    return details.get("release_date")


def map_movie(details: dict, max_cast: int = 10) -> dict:
    tmdb_id = details["id"]
    title = details.get("title") or details.get("original_title") or str(tmdb_id)
    slug = create_slug(title)
    actual_release_date = _extract_us_theatrical_release_date(details)

    return {
        "_id": f"movie_{slug}",

        "title": title,
        "original_title": details.get("original_title"),

        "year": (actual_release_date or "")[:4] or None,
        "release_date": actual_release_date,

        "runtime_minutes": details.get("runtime"),

        "genres": [g["name"] for g in details.get("genres", [])],

        "director": _extract_directors(details.get("credits")),
        "writers": _extract_writers(details.get("credits")),
        "cast": _extract_cast(details.get("credits"), limit=max_cast),

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

        "trailers": _extract_trailers(details.get("videos")),
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


def map_tv_series(details: dict, max_cast: int = 10) -> dict:
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

        "creators": _extract_creators(details),
        "cast": _extract_cast(details.get("credits"), limit=max_cast),

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

        "trailers": _extract_trailers(details.get("videos")),
        "status": details.get("status"),
        "tagline": details.get("tagline"),

        "content_type": "tv_series",

        "source_metadata": {
            "tmdb_id": tmdb_id,
        },

        "is_deleted": False,
        "deleted_at": None,
    }