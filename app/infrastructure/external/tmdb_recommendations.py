"""RecommendationSource for movies and TV: TMDb's recommendations for a title."""

import httpx

from app.domain.recommendations.entities import BaseTitle, Recommendation

TMDB_URL = "https://api.themoviedb.org/3"
IMAGE_URL = "https://image.tmdb.org/t/p/w342"
MIN_VOTES = 50  # skip obscure titles (and the low-profile adult releases that slip through)


class TmdbRecommendations:
    def __init__(self, api_key: str | None, content_type: str):  # "movie" or "tv_series"
        self._key = api_key
        self._content_type = content_type
        self._path = "movie" if content_type == "movie" else "tv"

    async def similar(self, base: BaseTitle, limit: int) -> list[Recommendation]:
        if not (self._key and base.external_id):
            return []
        async with httpx.AsyncClient(timeout=15) as http:
            r = await http.get(
                f"{TMDB_URL}/{self._path}/{base.external_id}/recommendations",
                params={"api_key": self._key},
            )
        r.raise_for_status()
        results = [
            x for x in r.json().get("results", [])
            if not x.get("adult") and (x.get("vote_count") or 0) >= MIN_VOTES
        ]
        recs = []
        for rank, x in enumerate(results[:limit]):
            date = x.get("release_date") or x.get("first_air_date") or ""
            recs.append(Recommendation(
                content_type=self._content_type,
                external_id=x["id"],
                title=x.get("title") or x.get("name"),
                votes=len(results) - rank,  # TMDb lists best matches first
                year=int(date[:4]) if date[:4].isdigit() else None,
                image=IMAGE_URL + x["poster_path"] if x.get("poster_path") else None,
            ))
        return recs
