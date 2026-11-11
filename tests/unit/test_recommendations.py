from app.application.recommendations.service import RecommendationService
from app.domain.recommendations.entities import BaseTitle, Recommendation
from app.domain.recommendations.rules import pick
from app.domain.search.entities import RankedHit, SearchDocument, SearchResults

BASE = BaseTitle("anime", "anime_frieren", "Frieren", 1)


def rec(title, votes, ext):
    return Recommendation("anime", ext, title, votes)


def test_pick_orders_by_votes_and_skips_base_and_franchise_repeats():
    recs = [rec("Naruto: Shippuden", 900, 3), rec("Naruto", 1000, 2), rec("Frieren Season 2", 500, 4),
            rec("Mushishi", 300, 5), rec("Frieren", 5000, 1), rec("Nobody", 0, 6)]
    assert [r.title for r in pick(recs, BASE, 5)] == ["Naruto", "Mushishi"]


class FakeSearch:
    async def search(self, query):
        doc = SearchDocument(kind="characters", id="char_x", title="Frieren")
        anime = SearchDocument(kind="anime", id="anime_frieren", title="Frieren")
        return SearchResults(by_kind={"characters": [RankedHit(doc, 0)], "anime": [RankedHit(anime, 1)]},
                             top=RankedHit(doc, 0))


class FakeCatalog:
    async def base_title(self, content_type, content_id):
        return BASE if content_id == "anime_frieren" else None

    async def link(self, recs):
        return recs


class FailingSource:
    async def similar(self, base, limit):
        raise RuntimeError("AniList down")


async def test_skips_non_title_hits_and_survives_a_failing_source():
    service = RecommendationService(FakeSearch(), FakeCatalog(), {"anime": FailingSource()})
    result = await service.similar_to("Frieren")
    assert result.base == BASE  # the character hit was skipped for the anime
    assert result.items == []
