import pytest
from datetime import datetime
from httpx import AsyncClient
from app.db.mongo import get_db

@pytest.fixture(autouse=True)
async def setup_test_data():
    db = get_db()
    today = datetime.utcnow()
    month = today.month
    day = today.day
    current_year = today.year
    past_year = current_year - 2
    
    # 1. Episode from a past year (should appear)
    await db["episodes"].insert_one({
        "_id": "ep_past",
        "anime_id": "test_anime_onthisday",
        "episode_number": 1,
        "title": "Past Episode",
        "release_date": f"{past_year}-{month:02d}-{day:02d}",
        "is_deleted": False
    })
    
    # 2. Episode from current year (should NOT appear, belongs in releases)
    await db["episodes"].insert_one({
        "_id": "ep_current",
        "anime_id": "test_anime_onthisday",
        "episode_number": 2,
        "title": "Current Episode",
        "release_date": f"{current_year}-{month:02d}-{day:02d}",
        "is_deleted": False
    })
    
    # 3. Chapter from a past year (should appear)
    await db["chapters"].insert_one({
        "_id": "ch_past",
        "manga_id": "test_manga_onthisday",
        "chapter_number": 1,
        "release_date": f"{past_year}-{month:02d}-{day:02d}",
        "is_deleted": False
    })

    # Dummy parent content
    await db["anime"].insert_one({
        "_id": "test_anime_onthisday",
        "title": {"english": "OnThisDay Anime"}
    })
    
    await db["manga"].insert_one({
        "_id": "test_manga_onthisday",
        "title": "OnThisDay Manga"
    })
    
    yield
    
    await db["episodes"].delete_many({"_id": {"$in": ["ep_past", "ep_current"]}})
    await db["chapters"].delete_many({"_id": "ch_past"})
    await db["anime"].delete_many({"_id": "test_anime_onthisday"})
    await db["manga"].delete_many({"_id": "test_manga_onthisday"})


@pytest.mark.asyncio
async def test_episode_anniversary_appears(client: AsyncClient):
    res = await client.get("/home/today")
    assert res.status_code == 200
    data = res.json()
    
    ep_anniversaries = data.get("episode_anniversaries", [])
    ep_ids = [ep["content_id"] for ep in ep_anniversaries]
    
    assert "ep_past" in ep_ids
    
    # Verify enrichment
    past_ep = next(ep for ep in ep_anniversaries if ep["content_id"] == "ep_past")
    assert past_ep["parent_title"] == "OnThisDay Anime"
    assert past_ep["years_ago"] == 2

@pytest.mark.asyncio
async def test_current_year_excluded(client: AsyncClient):
    res = await client.get("/home/today")
    assert res.status_code == 200
    data = res.json()
    
    ep_anniversaries = data.get("episode_anniversaries", [])
    ep_ids = [ep["content_id"] for ep in ep_anniversaries]
    
    assert "ep_current" not in ep_ids

@pytest.mark.asyncio
async def test_chapter_anniversary_appears(client: AsyncClient):
    res = await client.get("/home/today")
    assert res.status_code == 200
    data = res.json()
    
    ch_anniversaries = data.get("chapter_anniversaries", [])
    ch_ids = [ch["content_id"] for ch in ch_anniversaries]
    
    assert "ch_past" in ch_ids
    
    # Verify enrichment
    past_ch = next(ch for ch in ch_anniversaries if ch["content_id"] == "ch_past")
    assert past_ch["parent_title"] == "OnThisDay Manga"
    assert past_ch["years_ago"] == 2
