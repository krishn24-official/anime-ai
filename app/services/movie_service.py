from app.repositories.movie_repository import get_all_movies, get_movie_by_id


def _serialize(movie: dict) -> dict:
    movie = dict(movie)
    movie["id"] = movie.pop("_id")
    return movie


async def fetch_all_movies(page: int = 1, limit: int = 20):
    movies, total = await get_all_movies(page=page, limit=limit)

    return {
        "items": [_serialize(m) for m in movies],
        "total": total,
        "page": page,
        "limit": limit,
    }


async def fetch_movie(movie_id: str):
    movie = await get_movie_by_id(movie_id)
    if not movie:
        return None
    return _serialize(movie)