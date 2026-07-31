import pytest
from httpx import AsyncClient
from app.db.mongo import get_db

@pytest.fixture(autouse=True)
async def setup_test_data():
    db = get_db()
    
    # Insert anime & episode
    await db["anime"].insert_one({
        "_id": "test_anime_public",
        "title": {"english": "Test Anime Public"},
        "images": {"poster": "anime_poster.jpg"},
        "is_deleted": False
    })
    
    await db["episodes"].insert_one({
        "_id": "test_ep_public",
        "anime_id": "test_anime_public",
        "episode_number": 100,
        "title": "Public Episode",
        "summary": "Summary text",
        "is_deleted": False
    })
    
    await db["episodes"].insert_one({
        "_id": "test_ep_deleted",
        "anime_id": "test_anime_public",
        "episode_number": 101,
        "is_deleted": True
    })

    # Insert manga & chapter
    await db["manga"].insert_one({
        "_id": "test_manga_public",
        "title": "Test Manga Public",
        "images": {"poster": "manga_poster.jpg"},
        "is_deleted": False
    })
    
    await db["chapters"].insert_one({
        "_id": "test_ch_public",
        "manga_id": "test_manga_public",
        "chapter_number": 50,
        "summary": "Chapter summary",
        "is_deleted": False
    })
    
    await db["chapters"].insert_one({
        "_id": "test_ch_deleted",
        "manga_id": "test_manga_public",
        "chapter_number": 51,
        "is_deleted": True
    })
    
    yield
    
    await db["anime"].delete_many({"_id": "test_anime_public"})
    await db["episodes"].delete_many({"anime_id": "test_anime_public"})
    await db["manga"].delete_many({"_id": "test_manga_public"})
    await db["chapters"].delete_many({"manga_id": "test_manga_public"})

@pytest.mark.asyncio
async def test_get_episode_detail_success(client: AsyncClient):
    res = await client.get("/episodes/test_ep_public")
    assert res.status_code == 200
    data = res.json()
    assert data["episode_number"] == 100
    assert data["title"] == "Public Episode"
    assert data["parent_title"] == "Test Anime Public"
    assert data["parent_poster"] == "anime_poster.jpg"
    assert data["summary"] == "Summary text"

@pytest.mark.asyncio
async def test_get_episode_detail_not_found(client: AsyncClient):
    res = await client.get("/episodes/nonexistent_ep")
    assert res.status_code == 404

@pytest.mark.asyncio
async def test_get_episode_detail_soft_deleted(client: AsyncClient):
    res = await client.get("/episodes/test_ep_deleted")
    assert res.status_code == 404

@pytest.mark.asyncio
async def test_get_chapter_detail_success(client: AsyncClient):
    res = await client.get("/chapters/test_ch_public")
    assert res.status_code == 200
    data = res.json()
    assert data["chapter_number"] == 50
    assert data["parent_title"] == "Test Manga Public"
    assert data["parent_poster"] == "manga_poster.jpg"
    assert data["summary"] == "Chapter summary"

@pytest.mark.asyncio
async def test_get_chapter_detail_not_found(client: AsyncClient):
    res = await client.get("/chapters/nonexistent_ch")
    assert res.status_code == 404

@pytest.mark.asyncio
async def test_get_chapter_detail_soft_deleted(client: AsyncClient):
    res = await client.get("/chapters/test_ch_deleted")
    assert res.status_code == 404

@pytest.mark.asyncio
async def test_endpoints_require_no_auth(client: AsyncClient):
    # These endpoints are hit without any auth token (client fixture is unauthenticated by default)
    res_ep = await client.get("/episodes/test_ep_public")
    assert res_ep.status_code == 200
    
    res_ch = await client.get("/chapters/test_ch_public")
    assert res_ch.status_code == 200
