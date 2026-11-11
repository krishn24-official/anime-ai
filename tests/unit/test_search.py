"""Unit tests for search ranking rules and the search use case (no database)."""

import pytest

from app.application.search.service import SearchService
from app.domain.search import rules
from app.domain.search.entities import SearchDocument
from app.domain.search.ports import SearchIndexUnavailable
from app.domain.search.rules import MatchLevel, rank_of
from app.infrastructure.mongo.regex_search_index import (
    exact_pattern,
    fuzzy_pattern,
    word_prefix_pattern,
)
from app.infrastructure.search.fallback_index import FallbackSearchIndex


def doc(kind, title, *aliases, popularity=0.0, rating=0.0):
    return SearchDocument(
        kind=kind,
        id=f"{kind}_{rules.compact(title)}",
        title=title,
        aliases=tuple(aliases),
        popularity=popularity,
        rating=rating,
        display={"title": title},
    )


CATALOG = [
    doc("anime", "ONE PIECE", "OP", "One Piece"),
    doc("anime", "ONE PIECE FAN LETTER", rating=9.0),
    doc("anime", "Attack on Titan", "Shingeki no Kyojin", "AoT", "SnK"),
    doc("anime", "Gate"),
    doc("anime", "Gokujo."),
    doc("anime", "Naruto", "ナルト"),
    doc("anime", "Ao to Midori"),
    doc("movies", "Spider-Man", popularity=20918),
    doc("movies", "Spider-Man: No Way Home", popularity=19000),
    doc("movies", "Italian Spiderman", popularity=50),
    doc("characters", "Goku Son"),
    doc("characters", "Itachi Uchiha"),
    doc("characters", "Izuru Hitachi"),
    doc("actors", "León Artola"),
]


class FakeIndex:
    """Returns every document of the kind; the service must do all the filtering."""

    def __init__(self, docs=CATALOG):
        self.docs = docs
        self.calls = []

    async def candidates(self, query, kind, limit, fuzzy):
        self.calls.append((kind, fuzzy))
        return [d for d in self.docs if d.kind == kind]


def titles(results, kind):
    return [h.document.title for h in results.by_kind[kind]]


# ── Rules ────────────────────────────────────────────────────────────────────


def test_normalize_and_compact():
    assert rules.normalize("  Spider-Man: No Way Home ") == "spider man no way home"
    assert rules.normalize("Pokémon") == "pokemon"
    assert rules.compact("Spider-Man") == "spiderman"
    assert rules.normalize("ナルト") == "ナルト"


@pytest.mark.parametrize(
    "query, title, aliases, expected",
    [
        ("naruto", "Naruto", (), rank_of(MatchLevel.EXACT, False)),
        ("aot", "Attack on Titan", ("AoT",), rank_of(MatchLevel.EXACT, True)),
        ("spiderman", "Spider-Man", (), rank_of(MatchLevel.EXACT, False)),
        ("goku", "Goku Son", (), rank_of(MatchLevel.PREFIX_WORDS, False)),
        ("titan", "Attack on Titan", (), rank_of(MatchLevel.WORDS, False)),
        ("goku", "Gokujo.", (), rank_of(MatchLevel.PREFIX, False)),
        ("piec", "One Piece", (), rank_of(MatchLevel.WORD_PREFIX, False)),
        ("itachi", "Izuru Hitachi", (), rank_of(MatchLevel.CONTAINS, False)),
        ("aot", "Ao to Midori", (), None),  # partial match may not span words
        ("one", "Gate", (), None),  # the old subsequence regex matched this
    ],
)
def test_match_rank(query, title, aliases, expected):
    assert rules.match_rank(query, doc("anime", title, *aliases)) == expected


def test_typo_matching_is_opt_in_and_keeps_first_letter():
    naruto = doc("anime", "Naruto")
    assert rules.match_rank("narto", naruto) is None
    assert rules.match_rank("narto", naruto, allow_fuzzy=True) == rank_of(MatchLevel.FUZZY, False)
    assert rules.match_rank("barto", naruto, allow_fuzzy=True) is None


def test_exact_alias_beats_partial_title():
    assert rank_of(MatchLevel.EXACT, True) < rank_of(MatchLevel.PREFIX_WORDS, False)


def test_short_queries_get_fewer_results():
    assert rules.result_limit("op") == rules.SHORT_QUERY_LIMIT
    assert rules.result_limit("one") == rules.DEFAULT_LIMIT


# ── Use case ─────────────────────────────────────────────────────────────────


async def test_alias_finds_the_obvious_title():
    results = await SearchService(FakeIndex()).search("aot")
    assert titles(results, "anime") == ["Attack on Titan"]
    assert results.top.document.title == "Attack on Titan"


async def test_short_query_does_not_match_everything():
    results = await SearchService(FakeIndex()).search("op")
    assert titles(results, "anime") == ["ONE PIECE"]
    assert "Gate" not in titles(results, "anime")


async def test_shorter_title_beats_higher_rated_spin_off():
    results = await SearchService(FakeIndex()).search("one piece")
    assert titles(results, "anime")[:2] == ["ONE PIECE", "ONE PIECE FAN LETTER"]


async def test_popularity_orders_equal_matches():
    results = await SearchService(FakeIndex()).search("spider")
    assert titles(results, "movies") == ["Spider-Man", "Spider-Man: No Way Home", "Italian Spiderman"]


async def test_weak_matches_hidden_when_strong_exist():
    results = await SearchService(FakeIndex()).search("itachi")
    assert titles(results, "characters") == ["Itachi Uchiha"]


async def test_top_result_prefers_whole_word_match_across_kinds():
    results = await SearchService(FakeIndex()).search("goku")
    assert results.top.document.title == "Goku Son"


async def test_typo_fallback_only_when_nothing_strong():
    index = FakeIndex()
    results = await SearchService(index).search("narto")
    assert results.top.document.title == "Naruto"
    assert "León Artola" not in titles(results, "actors")
    assert any(fuzzy for _, fuzzy in index.calls)

    index = FakeIndex()
    await SearchService(index).search("naruto")
    assert not any(fuzzy for _, fuzzy in index.calls)


async def test_tiny_or_symbol_only_query_returns_nothing():
    index = FakeIndex()
    for q in ["", "a", " (( "]:
        results = await SearchService(index).search(q)
        assert results.top is None and not any(results.by_kind.values())
    assert index.calls == []


async def test_fallback_index_used_when_primary_unavailable():
    class Broken:
        async def candidates(self, *a):
            raise SearchIndexUnavailable("not built")

    results = await SearchService(FallbackSearchIndex(Broken(), FakeIndex())).search("naruto")
    assert results.top.document.title == "Naruto"


# ── Regex patterns (infrastructure, pure functions) ──────────────────────────


def test_regex_patterns_escape_user_input():
    assert exact_pattern("((") is None
    assert "\\(" not in (word_prefix_pattern("naruto (") or "")  # symbols dropped, not injected
    assert fuzzy_pattern("c++") is not None


# ── search_kind (paginated, one kind) ────────────────────────────────────────


async def test_search_kind_pages_through_ranked_results():
    docs = [doc("anime", t) for t in ["Naruto", "Naruto: Shippuden", "Boruto: Naruto Next Generations", "Gate"]]
    service = SearchService(FakeIndex(docs))

    page1, total = await service.search_kind("naruto", "anime", limit=2)
    page2, _ = await service.search_kind("naruto", "anime", limit=2, offset=2)

    assert total == 3  # "Gate" does not match
    assert [d.title for d in page1] == ["Naruto", "Naruto: Shippuden"]
    assert [d.title for d in page2] == ["Boruto: Naruto Next Generations"]


async def test_search_kind_applies_the_same_weak_and_typo_rules():
    service = SearchService(FakeIndex())
    assert [d.title for d in (await service.search_kind("itachi", "characters", 10))[0]] == ["Itachi Uchiha"]
    assert [d.title for d in (await service.search_kind("narto", "anime", 10))[0]] == ["Naruto"]


async def test_search_kind_rejects_unknown_kind_and_short_query():
    service = SearchService(FakeIndex())
    assert await service.search_kind("naruto", "podcasts", 10) == ([], 0)
    assert await service.search_kind("n", "anime", 10) == ([], 0)
