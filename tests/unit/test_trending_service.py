"""Unit tests for trending use cases and rules. In-memory fakes, no database."""

from datetime import timedelta, datetime, timezone

import pytest

from app.application.errors import InvalidInputError, NotFoundError
from app.application.trending.service import TrendingService
from app.domain.shared.content import ContentRef, ContentSummary
from app.domain.trending import rules
from app.domain.trending.entities import SearchCount, TrendingEntry
from app.services.title_matcher import find_matches, normalize_alias
from tests.fakes.trending import (
    FakeImageStorage,
    InMemoryCatalog,
    InMemorySignalRepository,
    InMemoryTrendingRepository,
)

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
NARUTO = ContentRef("anime", "anime_naruto")
BLEACH = ContentRef("anime", "anime_bleach")


def make_service(catalog_items=None, signals=None, images=None):
    entries = InMemoryTrendingRepository()
    service = TrendingService(
        entries=entries,
        signals=signals or InMemorySignalRepository(),
        catalog=InMemoryCatalog(
            catalog_items
            if catalog_items is not None
            else {
                NARUTO: ContentSummary("Naruto", "https://img/naruto.jpg"),
                BLEACH: ContentSummary("Bleach", None),
            }
        ),
        images=images or FakeImageStorage(),
        find_matches=find_matches,
        clock=lambda: NOW,
    )
    return service, entries




async def test_pin_creates_editors_pick_with_custom_poster():
    images = FakeImageStorage("https://img/custom.png")
    service, entries = make_service(images=images)

    await service.pin("anime", "anime_naruto", admin_id="admin1", note="New season", image_bytes=b"x")

    entry = entries.rows[NARUTO]
    assert entry.pinned and entry.reason == rules.EDITOR_PICK_REASON
    assert entry.score == rules.EDITOR_PICK_SCORE
    assert entry.custom_poster == "https://img/custom.png"
    assert images.uploads == [(b"x", rules.TRENDING_IMAGE_FOLDER)]


async def test_pin_rejects_unknown_type_and_missing_content():
    service, _ = make_service()
    with pytest.raises(InvalidInputError):
        await service.pin("podcast", "x", admin_id="a")
    with pytest.raises(NotFoundError):
        await service.pin("anime", "anime_does_not_exist", admin_id="a")


async def test_automatic_entries_never_overwrite_a_pin():
    signals = InMemorySignalRepository()
    service, entries = make_service(signals=signals)
    await service.pin("anime", "anime_naruto", admin_id="a")
    await signals.record_mention(NARUTO, "news1", "naruto", NOW)

    result = await service.recompute_news_trending(hours=48)

    assert result == {"trending_updated": 0}
    assert entries.rows[NARUTO].source == "manual"


async def test_list_trending_enriches_and_custom_poster_wins():
    service, _ = make_service(images=FakeImageStorage("https://img/custom.png"))
    await service.pin("anime", "anime_naruto", admin_id="a", image_bytes=b"x")
    await service.pin("anime", "anime_bleach", admin_id="a")

    items = {i.content_id: i for i in await service.list_trending(limit=10)}

    assert items["anime_naruto"].title == "Naruto"
    assert items["anime_naruto"].poster_image == "https://img/custom.png"
    assert items["anime_bleach"].poster_image is None


async def test_list_trending_falls_back_to_id_and_hides_expired():
    service, entries = make_service(catalog_items={})
    await entries.save(
        TrendingEntry(NARUTO, "news", "r", 5.0, False, NOW, expires_at=NOW + timedelta(hours=1))
    )
    await entries.save(
        TrendingEntry(BLEACH, "news", "r", 9.0, False, NOW, expires_at=NOW - timedelta(hours=1))
    )

    items = await service.list_trending()

    assert [i.content_id for i in items] == ["anime_naruto"]
    assert items[0].title == "anime_naruto"


async def test_repinning_keeps_previous_note_when_none_given():
    service, entries = make_service()
    await service.pin("anime", "anime_naruto", admin_id="a", note="Trailer out")
    await service.pin("anime", "anime_naruto", admin_id="a")
    assert entries.rows[NARUTO].note == "Trailer out"


async def test_scan_article_records_each_mention_once():
    signals = InMemorySignalRepository()
    service, _ = make_service(signals=signals)
    alias_index = [("naruto", "anime", "anime_naruto"), ("bleach", "anime", "anime_bleach")]

    await service.scan_article_for_mentions("n1", "Naruto and Bleach", "", alias_index)
    await service.scan_article_for_mentions("n1", "Naruto again", "", alias_index)

    assert signals.mentions == {(NARUTO, "n1"), (BLEACH, "n1")}


@pytest.mark.parametrize(
    "counts, expected_qualified, expected_threshold",
    [
        ([8, 8, 8, 100], 1, 62.0),  # avg 31 -> threshold 62
        ([1, 2], 0, 15),  # never below MIN_SEARCH_THRESHOLD
    ],
)
async def test_recompute_search_trending_threshold(counts, expected_qualified, expected_threshold):
    canned = [SearchCount(ContentRef("anime", f"item{i}"), c) for i, c in enumerate(counts)]
    service, _ = make_service(signals=InMemorySignalRepository(searches=canned))

    summary = await service.recompute_search_trending(hours=3)

    assert summary == {
        "evaluated": len(counts),
        "qualified": expected_qualified,
        "threshold_used": expected_threshold,
    }


def test_news_reason_pluralisation():
    assert rules.news_reason(1) == "Mentioned in 1 article this week"
    assert rules.news_reason(3) == "Mentioned in 3 articles this week"


# ── Title matcher (pure functions) ───────────────────────────────────────────


def test_normalize_alias():
    assert normalize_alias("  Naruto   Shippuden  ") == "naruto shippuden"
    assert normalize_alias("The") == "the"


def test_find_matches_prefers_longest_alias_per_content():
    alias_index = [
        ("naruto shippuden", "anime", "1"),
        ("naruto", "anime", "1"),
        ("bleach", "anime", "2"),
    ]
    matches = find_matches("I love watching Naruto Shippuden and Bleach.", alias_index)
    assert sorted(m[0] for m in matches) == ["bleach", "naruto shippuden"]
