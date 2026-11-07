"""Integration tests for the MongoDB trending repositories (uses the test database)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.db.mongo import get_db
from app.domain.shared.content import ContentRef
from app.domain.trending.entities import TrendingEntry
from app.infrastructure.mongo.trending_repository import (
    MongoTrendingRepository,
    MongoTrendingSignalRepository,
)

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
NARUTO = ContentRef("anime", "anime_naruto")
BLEACH = ContentRef("anime", "anime_bleach")



@pytest.fixture
def mongo_repos():
    return MongoTrendingRepository(get_db), MongoTrendingSignalRepository(get_db)


async def test_mongo_repository_roundtrip_and_ordering(mongo_repos):
    repo, _ = mongo_repos
    pinned = TrendingEntry(NARUTO, "manual", "Editor's Pick", 1000.0, True, NOW, note="n")
    auto = TrendingEntry(BLEACH, "news", "r", 3.0, False, NOW, expires_at=NOW + timedelta(days=1))
    await repo.save(auto)
    await repo.save(pinned)

    active = await repo.list_active(NOW, limit=10)
    assert [e.content for e in active[:2]] == [NARUTO, BLEACH]
    assert (await repo.get(NARUTO)).note == "n"

    await repo.delete(NARUTO)
    await repo.delete(BLEACH)
    assert await repo.get(NARUTO) is None


async def test_mongo_mentions_are_deduplicated(mongo_repos):
    _, signals = mongo_repos
    await signals.record_mention(NARUTO, "news_123", "naruto", NOW)
    await signals.record_mention(NARUTO, "news_123", "naruto 2", NOW)  # ignored
    counts = {c.content: c.mention_count for c in await signals.mention_counts(NOW - timedelta(hours=1))}
    assert counts[NARUTO] == 1


async def test_mongo_search_counts_distinct_users(mongo_repos):
    _, signals = mongo_repos
    for _ in range(5):
        await signals.record_search_click(BLEACH, "q", "userA", NOW)
    await signals.record_search_click(BLEACH, "q", "userB", NOW)
    counts = {c.content: c.distinct_searcher_count for c in await signals.search_counts(NOW - timedelta(hours=1))}
    assert counts[BLEACH] == 2
