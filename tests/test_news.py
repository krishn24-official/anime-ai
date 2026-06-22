import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock
from app.db.mongo import get_db
from app.services.news_pipeline_service import run_news_pipeline

pytestmark = pytest.mark.asyncio

# Mock source data for pipeline testing
MOCK_ARTICLES = [
    {
        "title": "Fresh Anime Corner Article",
        "url": "https://animecorner.me/fresh-article",
        "source": "animecorner",
        "description": "This is a fresh anime news article content.",
        "published_at": datetime.now(timezone.utc) - timedelta(hours=2),
        "image_url": "https://example.com/image1.jpg"
    },
    {
        "title": "Stale Crunchyroll Article",
        "url": "https://crunchyroll.com/stale-article",
        "source": "crunchyroll",
        "description": "This is an old crunchyroll article.",
        "published_at": datetime.now(timezone.utc) - timedelta(hours=30),  # > 24 hours
        "image_url": "https://example.com/image2.jpg"
    },
    {
        "title": "Unmapped Source Article",
        "url": "https://unmapped.com/article",
        "source": "unknown_source",
        "description": "This source is not mapped to any category.",
        "published_at": datetime.now(timezone.utc) - timedelta(hours=1),
        "image_url": "https://example.com/image3.jpg"
    },
    {
        "title": "Fresh YouTube Game News",
        "url": "https://youtube.com/watch?v=123",
        "source": "youtube",
        "youtube_channel": "IGN",
        "description": "Fresh gaming news from IGN.",
        "published_at": datetime.now(timezone.utc) - timedelta(hours=4),
        "image_url": "https://example.com/image4.jpg"
    }
]

async def dummy_fetch_animecorner_news():
    return [MOCK_ARTICLES[0], MOCK_ARTICLES[1]]

async def dummy_fetch_youtube_news():
    return [MOCK_ARTICLES[3]]

async def dummy_fetch_empty():
    return []

@pytest.fixture
def mock_news_sources():
    # Patch the SOURCES in the news_pipeline_service to use our dummy fetch functions
    with patch("app.services.news_pipeline_service.SOURCES", [
        dummy_fetch_animecorner_news,
        dummy_fetch_youtube_news,
        dummy_fetch_empty,  # representing other sources returning nothing
    ]):
        yield

async def test_run_news_pipeline(mock_news_sources):
    # Mock web fetch for full article content to avoid network calls
    with patch("app.services.news_pipeline_service.fetch_full_article_content", new_callable=AsyncMock) as mock_content:
        mock_content.return_value = "Full fetched page content details."
        
        summary = await run_news_pipeline()
        
        assert summary["fetched"] == 3  # 2 from animecorner, 1 from youtube
        assert summary["fresh"] == 2    # Fresh Anime Corner + IGN YouTube (Crunchyroll is >24h)
        assert summary["saved"] == 2    # Unmapped/stale skipped
        assert summary["skipped_unmapped"] == 0 # unknown source was not returned by patched SOURCES
        
        # Verify stored in DB
        db = get_db()
        articles = await db["news"].find().to_list(None)
        assert len(articles) == 2
        
        # Check field values
        ac_art = next(a for a in articles if a["source"] == "animecorner")
        assert ac_art["title"] == "Fresh Anime Corner Article"
        assert ac_art["category"] == "Anime"
        assert ac_art["summary"] == "Full fetched page content details."[:240]

        yt_art = next(a for a in articles if a["source"] == "youtube")
        assert yt_art["title"] == "Fresh YouTube Game News"
        assert yt_art["category"] == "Games"

async def test_news_apis(client, mock_news_sources):
    with patch("app.services.news_pipeline_service.fetch_full_article_content", new_callable=AsyncMock) as mock_content:
        mock_content.return_value = "Short summary content."
        await run_news_pipeline()

    # Get Latest news
    resp = await client.get("/news/latest?limit=5")
    assert resp.status_code == 200
    latest = resp.json()
    assert len(latest) == 2
    assert latest[0]["title"] in ["Fresh Anime Corner Article", "Fresh YouTube Game News"]

    # Filter by category Anime
    resp = await client.get("/news?category=Anime")
    assert resp.status_code == 200
    anime_news = resp.json()
    assert anime_news["total"] == 1
    assert anime_news["items"][0]["category"] == "Anime"

    # Filter by category Games
    resp = await client.get("/news?category=Games")
    assert resp.status_code == 200
    games_news = resp.json()
    assert games_news["total"] == 1
    assert games_news["items"][0]["category"] == "Games"

    # Retrieve news detail
    article_id = anime_news["items"][0]["id"]
    resp = await client.get(f"/news/{article_id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Fresh Anime Corner Article"

    # Retrieve non-existent detail
    resp = await client.get("/news/60ba42c12a7f5d001bfa0000")
    assert resp.status_code == 404

async def test_admin_manual_news_crud(client):
    # Setup test admin user
    db = get_db()
    admin_user = {
        "email": "admin@example.com",
        "username": "adminuser",
        "password_hash": "dummy_hash",
        "is_admin": True,
        "is_active": True,
        "created_at": datetime.now(timezone.utc)
    }
    res = await db["users"].insert_one(admin_user)
    admin_id = str(res.inserted_id)

    # Login to get JWT
    with patch("app.services.user_service.verify_password", return_value=True):
        login_resp = await client.post("/auth/login", json={
            "identifier": "admin@example.com",
            "password": "anypassword"
        })
        assert login_resp.status_code == 200
        access_token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

    # Test creating manual news post
    with patch("app.services.manual_news_service.upload_image_from_bytes", new_callable=AsyncMock) as mock_upload:
        mock_upload.return_value = "https://cloudinary.com/dummy.jpg"
        
        post_data = {
            "title": "Manual Test Title",
            "description": "Manual Test Description text content is here.",
            "category": "Games"
        }
        
        # Files parameter can be empty or mocked
        create_resp = await client.post(
            "/admin/news", 
            data=post_data,
            headers=headers
        )
        assert create_resp.status_code == 200
        news_data = create_resp.json()
        assert news_data["title"] == "Manual Test Title"
        assert news_data["category"] == "Games"
        assert news_data["source"] == "manual"
        news_id = news_data["id"]

    # Test updating manual news post
    update_data = {
        "title": "Updated Manual Title",
        "description": "Updated Description content.",
        "category": "Anime"
    }
    update_resp = await client.put(
        f"/admin/news/{news_id}",
        data=update_data,
        headers=headers
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "Updated Manual Title"
    assert update_resp.json()["category"] == "Anime"

    # Test deleting manual news post
    delete_resp = await client.delete(
        f"/admin/news/{news_id}",
        headers=headers
    )
    assert delete_resp.status_code == 200
    assert delete_resp.json()["message"] == "News post deleted"

    # Verify deleted
    verify_resp = await client.get(f"/news/{news_id}")
    assert verify_resp.status_code == 404
