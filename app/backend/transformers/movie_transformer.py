from app.backend.utils.slug import create_slug


def _parse_runtime(runtime_str: str | None) -> int | None:
    if not runtime_str or runtime_str == "N/A":
        return None
    try:
        return int(runtime_str.replace(" min", "").strip())
    except (ValueError, AttributeError):
        return None


def _parse_imdb_rating(rating_str: str | None) -> float | None:
    if not rating_str or rating_str == "N/A":
        return None
    try:
        return float(rating_str)
    except ValueError:
        return None


def _parse_list(value: str | None) -> list[str]:
    if not value or value == "N/A":
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def transform_movie(data: dict) -> dict:
    title = data.get("Title", "")
    slug = create_slug(title)

    poster = data.get("Poster")
    if poster == "N/A":
        poster = None

    return {
        "_id": f"movie_{slug}",

        "title": title,

        "year": data.get("Year"),

        "release_date": data.get("Released") if data.get("Released") != "N/A" else None,

        "runtime_minutes": _parse_runtime(data.get("Runtime")),

        "genres": _parse_list(data.get("Genre")),

        "director": _parse_list(data.get("Director")),

        "writers": _parse_list(data.get("Writer")),

        "cast": _parse_list(data.get("Actors")),

        "plot": data.get("Plot") if data.get("Plot") != "N/A" else None,

        "language": _parse_list(data.get("Language")),

        "country": _parse_list(data.get("Country")),

        "rating": {
            "imdb": _parse_imdb_rating(data.get("imdbRating")),
            "imdb_votes": data.get("imdbVotes") if data.get("imdbVotes") != "N/A" else None,
        },

        "images": {
            "poster": poster,
        },

        "box_office": data.get("BoxOffice") if data.get("BoxOffice") != "N/A" else None,

        "content_type": "movie",

        "source_metadata": {
            "imdb_id": data.get("imdbID"),
        },

        "is_deleted": False,
        "deleted_at": None,
    }