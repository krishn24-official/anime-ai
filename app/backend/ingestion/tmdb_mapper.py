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


def map_movie(details: dict) -> dict:
    tmdb_id = details["id"]
    slug = create_slug(details.get("title") or details.get("original_title") or str(tmdb_id))

    return {
        "_id": f"movie_{slug}",
        "tmdb_id": tmdb_id,
        "title": details.get("title"),
        "original_title": details.get("original_title"),
        "overview": details.get("overview"),
        "poster": image_url(details.get("poster_path")),
        "backdrop": image_url(details.get("backdrop_path"), "w1280"),
        "release_date": details.get("release_date"),
        "runtime": details.get("runtime"),
        "genres": [g["name"] for g in details.get("genres", [])],
        "tmdb_rating": details.get("vote_average"),
        "tmdb_vote_count": details.get("vote_count"),
        "cast": _extract_cast(details.get("credits")),
        "trailer_url": _extract_trailer(details.get("videos")),
        "status": details.get("status"),
        "content_type": "movie",
    }


def map_tv_series(details: dict) -> dict:
    tmdb_id = details["id"]
    slug = create_slug(details.get("name") or details.get("original_name") or str(tmdb_id))

    return {
        "_id": f"tv_{slug}",
        "tmdb_id": tmdb_id,
        "title": details.get("name"),
        "original_title": details.get("original_name"),
        "overview": details.get("overview"),
        "poster": image_url(details.get("poster_path")),
        "backdrop": image_url(details.get("backdrop_path"), "w1280"),
        "first_air_date": details.get("first_air_date"),
        "last_air_date": details.get("last_air_date"),
        "number_of_seasons": details.get("number_of_seasons"),
        "number_of_episodes": details.get("number_of_episodes"),
        "episode_runtime": (details.get("episode_run_time") or [None])[0],
        "genres": [g["name"] for g in details.get("genres", [])],
        "tmdb_rating": details.get("vote_average"),
        "tmdb_vote_count": details.get("vote_count"),
        "cast": _extract_cast(details.get("credits")),
        "trailer_url": _extract_trailer(details.get("videos")),
        "status": details.get("status"),
        "content_type": "tv_series",
    }