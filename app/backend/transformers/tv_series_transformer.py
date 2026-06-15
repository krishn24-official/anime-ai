from app.backend.utils.slug import create_slug
from app.backend.transformers.movie_transformer import (
    _parse_runtime,
    _parse_imdb_rating,
    _parse_list,
)


def transform_tv_series(data: dict) -> dict:
    title = data.get("Title", "")
    slug = create_slug(title)

    poster = data.get("Poster")
    if poster == "N/A":
        poster = None

    total_seasons = data.get("totalSeasons")
    try:
        total_seasons = int(total_seasons) if total_seasons and total_seasons != "N/A" else None
    except ValueError:
        total_seasons = None

    return {
        "_id": f"tv_{slug}",

        "title": title,

        "year": data.get("Year"),

        "first_air_date": data.get("Released") if data.get("Released") != "N/A" else None,

        "episode_runtime_minutes": _parse_runtime(data.get("Runtime")),

        "genres": _parse_list(data.get("Genre")),

        "creators": _parse_list(data.get("Writer")),

        "cast": _parse_list(data.get("Actors")),

        "plot": data.get("Plot") if data.get("Plot") != "N/A" else None,

        "language": _parse_list(data.get("Language")),

        "country": _parse_list(data.get("Country")),

        "total_seasons": total_seasons,

        "rating": {
            "imdb": _parse_imdb_rating(data.get("imdbRating")),
            "imdb_votes": data.get("imdbVotes") if data.get("imdbVotes") != "N/A" else None,
        },

        "images": {
            "poster": poster,
        },

        "status": None,

        "content_type": "tv_series",

        "source_metadata": {
            "imdb_id": data.get("imdbID"),
        },

        "is_deleted": False,
        "deleted_at": None,
    }