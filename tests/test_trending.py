import pytest
from app.repositories.trending_repository import (
    upsert_trending,
    get_active_trending,
    remove_trending,
    record_mention,
    get_mention_counts,
    record_search_click,
    get_search_counts
)
from app.services.title_matcher import (
    normalize_alias,
    find_matches
)
from app.services.trending_service import (
    get_trending_content,
    recompute_search_trending
)

@pytest.mark.asyncio
async def test_trending_manual_pin_protection():
    # Cleanup before test
    await remove_trending("anime", "test_anime_1")

    # 1. Manually pin an item
    success = await upsert_trending(
        content_type="anime",
        content_id="test_anime_1",
        source="manual",
        reason="Editor's Pick",
        score=1000.0,
        pinned=True
    )
    assert success is True

    # 2. Check it appears
    active = await get_active_trending(limit=10)
    
    # find our item
    item = next((x for x in active if x["content_id"] == "test_anime_1"), None)
    assert item is not None
    assert item["pinned"] is True
    assert item["score"] == 1000.0

    # 3. Attempt to overwrite with an auto-job (pinned=False)
    success_auto = await upsert_trending(
        content_type="anime",
        content_id="test_anime_1",
        source="auto_scoring",
        reason="Trending",
        score=500.0,
        pinned=False
    )
    assert success_auto is False # Should be rejected

    # 4. Verify original pinned item remains unchanged
    active_again = await get_active_trending(limit=10)
    item_again = next((x for x in active_again if x["content_id"] == "test_anime_1"), None)
    assert item_again["score"] == 1000.0
    assert item_again["source"] == "manual"
    
    # Cleanup after test
    await remove_trending("anime", "test_anime_1")

@pytest.mark.asyncio
async def test_trending_custom_poster_priority():
    # Cleanup before test
    await remove_trending("anime", "test_anime_1")

    # 1. Pin an item with custom_poster
    success = await upsert_trending(
        content_type="anime",
        content_id="test_anime_1",
        source="manual",
        reason="Editor's Pick",
        score=1000.0,
        pinned=True,
        custom_poster="https://cloudinary.com/custom.png"
    )
    assert success is True

    # 2. Check get_trending_content fallback logic
    # Even if resolve_content_title returns something (or None), custom_poster must win
    enriched = await get_trending_content(limit=10)
    
    # find our item
    item = next((x for x in enriched if x["content_id"] == "test_anime_1"), None)
    assert item is not None
    assert item["poster_image"] == "https://cloudinary.com/custom.png"

    # Cleanup after test
    await remove_trending("anime", "test_anime_1")

def test_normalize_alias():
    assert normalize_alias("  Naruto   Shippuden  ") == "naruto shippuden"
    assert normalize_alias("The") == "the"

def test_find_matches():
    alias_index = [
        ("naruto shippuden", "anime", "1"),
        ("naruto", "anime", "1"),
        ("bleach", "anime", "2")
    ]
    
    text = "I love watching Naruto Shippuden and Bleach."
    matches = find_matches(text, alias_index)
    
    # Should match longest first, then skip the shorter substring for the SAME content_id
    # so we expect ("naruto shippuden", "anime", "1") and ("bleach", "anime", "2")
    # but NOT ("naruto", "anime", "1")
    
    assert len(matches) == 2
    matched_aliases = [m[0] for m in matches]
    assert "naruto shippuden" in matched_aliases
    assert "bleach" in matched_aliases
    assert "naruto" not in matched_aliases

@pytest.mark.asyncio
async def test_record_mention_duplicates():
    # Attempting to record the exact same mention twice should gracefully do nothing on the second try
    # due to the unique index on (content_id, news_id).
    
    await record_mention("anime", "test_anime_x", "news_123", "test")
    # This second one should be silently ignored (DuplicateKeyError caught)
    await record_mention("anime", "test_anime_x", "news_123", "test2")
    
    # Clean up (we don't strictly have a delete_mention function exposed, so we'll just test that it didn't throw)
    pass

@pytest.mark.asyncio
async def test_search_counts_distinct_users():
    # Insert 5 clicks from the same user
    for _ in range(5):
        await record_search_click("anime", "search_anime_1", "query1", "userA")
    # Insert 1 click from a different user
    await record_search_click("anime", "search_anime_1", "query1", "userB")
    
    # Check counts
    counts = await get_search_counts(hours=3)
    item_counts = {c["content_id"]: c["distinct_searcher_count"] for c in counts}
    
    # Should be exactly 2 distinct searchers, despite 6 total clicks
    assert item_counts.get("search_anime_1") == 2

@pytest.mark.asyncio
async def test_recompute_search_trending_thresholds(monkeypatch):
    # We will mock get_search_counts to return a controlled list.
    # MIN_SEARCH_THRESHOLD is 15.
    
    mock_counts = [
        {"content_type": "anime", "content_id": "low_traffic", "distinct_searcher_count": 8},
        {"content_type": "anime", "content_id": "low_traffic_2", "distinct_searcher_count": 8},
        {"content_type": "anime", "content_id": "low_traffic_3", "distinct_searcher_count": 8},
        {"content_type": "anime", "content_id": "high_traffic", "distinct_searcher_count": 100},
    ]
    
    async def mock_get_counts(hours):
        return mock_counts
        
    monkeypatch.setattr("app.services.trending_service.get_search_counts", mock_get_counts)
    
    summary = await recompute_search_trending(hours=3)
    
    assert summary["evaluated"] == 4
    assert summary["qualified"] == 1
    pass

@pytest.mark.asyncio
async def test_recompute_search_trending_qualifying(monkeypatch):
    mock_counts = [
        {"content_type": "anime", "content_id": "item1", "distinct_searcher_count": 8},
        {"content_type": "anime", "content_id": "item2", "distinct_searcher_count": 8},
        {"content_type": "anime", "content_id": "item3", "distinct_searcher_count": 8},
        {"content_type": "anime", "content_id": "item4", "distinct_searcher_count": 100},
    ]
    
    async def mock_get_counts(hours):
        return mock_counts
        
    monkeypatch.setattr("app.services.trending_service.get_search_counts", mock_get_counts)
    
    summary = await recompute_search_trending(hours=3)
    
    # Average = 124 / 4 = 31.
    # Threshold = max(15, 31 * 2) = 62.
    # Item4 (100) >= 62, so it qualifies.
    assert summary["qualified"] == 1
    assert summary["threshold_used"] == 62.0


