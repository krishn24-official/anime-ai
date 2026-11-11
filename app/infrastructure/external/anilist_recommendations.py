"""RecommendationSource for anime and manga: AniList's user-voted recommendations."""

import httpx

from app.domain.recommendations.entities import BaseTitle, Recommendation

ANILIST_URL = "https://graphql.anilist.co"
QUERY = """query ($id: Int, $search: String, $type: MediaType, $perPage: Int) {
  Media(id: $id, search: $search, type: $type) {
    recommendations(sort: RATING_DESC, perPage: $perPage) {
      nodes { rating mediaRecommendation {
        id isAdult seasonYear startDate { year }
        title { english romaji } coverImage { large }
      } }
    }
  }
}"""


class AniListRecommendations:
    def __init__(self, media_type: str):  # "ANIME" or "MANGA"
        self._type = media_type
        self._content_type = media_type.lower()

    async def similar(self, base: BaseTitle, limit: int) -> list[Recommendation]:
        variables = {"type": self._type, "perPage": limit}
        variables.update({"id": base.external_id} if base.external_id else {"search": base.title})
        async with httpx.AsyncClient(timeout=15) as http:
            r = await http.post(ANILIST_URL, json={"query": QUERY, "variables": variables})
        r.raise_for_status()
        media = (r.json().get("data") or {}).get("Media") or {}
        recs = []
        for node in (media.get("recommendations") or {}).get("nodes") or []:
            m = node.get("mediaRecommendation")
            if not m or m.get("isAdult"):
                continue
            recs.append(Recommendation(
                content_type=self._content_type,
                external_id=m["id"],
                title=m["title"].get("english") or m["title"].get("romaji"),
                votes=node.get("rating") or 0,
                year=m.get("seasonYear") or (m.get("startDate") or {}).get("year"),
                image=(m.get("coverImage") or {}).get("large"),
            ))
        return recs
