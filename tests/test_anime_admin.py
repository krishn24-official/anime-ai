import pytest
from app.services.anime_admin_service import parse_release_date, derive_season, create_anime, update_anime, delete_anime
from app.repositories import anime_repository
from app.repositories.content_repository import get_announced_releases_range, get_dated_releases_range
from app.db.mongo import get_db
import datetime

def test_parse_release_date():
    # Day requires month and year
    with pytest.raises(ValueError):
        parse_release_date(day=15, month=None, year=2026, precision="day")
    
    # Month requires year
    with pytest.raises(ValueError):
        parse_release_date(day=None, month=10, year=None, precision="month")
        
    # Month cannot have day
    with pytest.raises(ValueError):
        parse_release_date(day=15, month=10, year=2026, precision="month")
        
    # Year cannot have month or day
    with pytest.raises(ValueError):
        parse_release_date(day=None, month=10, year=2026, precision="year")
        
    # Valid day
    res = parse_release_date(day=15, month=10, year=2026, precision="day")
    assert res == {"day": 15, "month": 10, "year": 2026, "precision": "day"}
    
    # Valid month
    res = parse_release_date(day=None, month=10, year=2026, precision="month")
    assert res == {"day": None, "month": 10, "year": 2026, "precision": "month"}
    
    # Valid year
    res = parse_release_date(day=None, month=None, year=2026, precision="year")
    assert res == {"day": None, "month": None, "year": 2026, "precision": "year"}

def test_derive_season():
    assert derive_season(1) == "Winter"
    assert derive_season(4) == "Spring"
    assert derive_season(7) == "Summer"
    assert derive_season(10) == "Fall"
    assert derive_season(None) is None

@pytest.mark.asyncio
async def test_end_date_logic():
    db = get_db()
    await db["anime"].delete_many({"_id": {"$in": ["anime_end_date_test", "anime_end_date_invalid"]}})
    
    # 1. create_anime without end date
    content_id = await create_anime(
        admin_id="admin_123",
        title_english="End Date Test",
        title_romaji=None,
        title_japanese=None,
        synonyms=[],
        anime_type="TV",
        released=True,
        sub_status="ongoing",
        genres=[],
        studios=[],
        source="Original",
        episodes=12,
        duration=24,
        day=1,
        month=1,
        year=2024,
        precision="day",
        poster_bytes=None,
        banner_bytes=None
    )
    
    doc = await db["anime"].find_one({"_id": content_id})
    assert doc["end_date"] is None
    
    # 2. update_anime to add valid end date
    await update_anime(
        admin_id="admin_123",
        content_id=content_id,
        end_day=1,
        end_month=3,
        end_year=2024,
        end_precision="day"
    )
    doc = await db["anime"].find_one({"_id": content_id})
    assert doc["end_date"]["year"] == 2024
    assert doc["end_date"]["month"] == 3
    assert doc["end_date"]["day"] == 1
    
    # 3. update_anime to add invalid end date (before start)
    with pytest.raises(ValueError, match="end_date cannot be before the start release_date"):
        await update_anime(
            admin_id="admin_123",
            content_id=content_id,
            end_day=31,
            end_month=12,
            end_year=2023,
            end_precision="day"
        )
        
    # 4. update_anime to clear end date
    await update_anime(
        admin_id="admin_123",
        content_id=content_id,
        clear_end_date=True
    )
    doc = await db["anime"].find_one({"_id": content_id})
    assert doc["end_date"] is None
    
    # 5. create_anime with invalid end date (before start)
    with pytest.raises(ValueError, match="end_date cannot be before the start release_date"):
        await create_anime(
            admin_id="admin_123",
            title_english="End Date Invalid",
            title_romaji=None,
            title_japanese=None,
            synonyms=[],
            anime_type="TV",
            released=True,
            sub_status="ongoing",
            genres=[],
            studios=[],
            source="Original",
            episodes=12,
            duration=24,
            day=1,
            month=1,
            year=2024,
            precision="day",
            poster_bytes=None,
            banner_bytes=None,
            end_day=31,
            end_month=12,
            end_year=2023,
            end_precision="day"
        )
        
    await db["anime"].delete_many({"_id": {"$in": ["anime_end_date_test", "anime_end_date_invalid"]}})

@pytest.mark.asyncio
async def test_create_duplicate_slug_protection():
    db = get_db()
    # Ensure clean state
    await db["anime"].delete_many({"_id": "anime_test_dup_anime"})
    
    # Create first one
    await create_anime(
        admin_id="admin_1",
        title_english="Test Dup Anime",
        title_romaji=None,
        title_japanese=None,
        synonyms=[],
        anime_type="TV",
        released=False,
        sub_status="",
        genres=[],
        studios=[],
        source="Original",
        episodes=12,
        duration=24,
        day=None,
        month=None,
        year=2026,
        precision="year",
        poster_bytes=None,
        banner_bytes=None
    )
    
    # Try to create again
    with pytest.raises(ValueError, match="already exists"):
        await create_anime(
            admin_id="admin_1",
            title_english="Test Dup Anime",
            title_romaji=None,
            title_japanese=None,
            synonyms=[],
            anime_type="TV",
            released=False,
            sub_status="",
            genres=[],
            studios=[],
            source="Original",
            episodes=12,
            duration=24,
            day=None,
            month=None,
            year=2026,
            precision="year",
            poster_bytes=None,
            banner_bytes=None
        )
        
    # Soft delete it
    await delete_anime("anime_test_dup_anime")
    
    # Try to create again (should still fail because slug exists even if deleted)
    with pytest.raises(ValueError, match="already exists"):
        await create_anime(
            admin_id="admin_1",
            title_english="Test Dup Anime",
            title_romaji=None,
            title_japanese=None,
            synonyms=[],
            anime_type="TV",
            released=False,
            sub_status="",
            genres=[],
            studios=[],
            source="Original",
            episodes=12,
            duration=24,
            day=None,
            month=None,
            year=2026,
            precision="year",
            poster_bytes=None,
            banner_bytes=None
        )

@pytest.mark.asyncio
async def test_create_anime_source_metadata():
    db = get_db()
    await db["anime"].delete_many({"_id": "anime_metadata_test"})
    
    content_id = await create_anime(
        admin_id="admin_123",
        title_english="Metadata Test",
        title_romaji=None,
        title_japanese=None,
        synonyms=[],
        anime_type="TV",
        released=False,
        sub_status="",
        genres=[],
        studios=[],
        source="Original",
        episodes=None,
        duration=None,
        day=None,
        month=None,
        year=2026,
        precision="year",
        poster_bytes=None,
        banner_bytes=None
    )
    
    doc = await db["anime"].find_one({"_id": content_id})
    assert doc is not None
    assert "anilist_id" not in doc
    assert doc.get("source_metadata") == {"source": "manual", "created_by": "admin_123"}
    assert doc.get("is_deleted") is False

@pytest.mark.asyncio
async def test_soft_delete_anime():
    db = get_db()
    await db["anime"].delete_many({"_id": "anime_delete_test"})
    await db["anime"].insert_one({"_id": "anime_delete_test", "is_deleted": False})
    
    await delete_anime("anime_delete_test")
    
    doc = await db["anime"].find_one({"_id": "anime_delete_test"})
    assert doc["is_deleted"] is True
    assert doc["deleted_at"] is not None

@pytest.mark.asyncio
async def test_get_upcoming_seasonal_with_new_fields():
    db = get_db()
    await db["anime"].delete_many({"_id": {"$in": ["anime_legacy", "anime_new_day", "anime_new_month"]}})
    
    # Insert legacy format
    await db["anime"].insert_one({
        "_id": "anime_legacy",
        "title": {"english": "Legacy Anime"},
        "status": "upcoming",
        "year": 2026,
        "season": "Spring",
        "is_deleted": False
    })
    
    # Insert new format with month precision
    await db["anime"].insert_one({
        "_id": "anime_new_month",
        "title": {"english": "New Month Anime"},
        "status": "upcoming",
        "release_date": {"year": 2026, "month": 3, "day": None, "precision": "month"},
        "year": 2026,
        "season": "Spring",
        "is_deleted": False
    })
    
    # Insert new format with day precision
    await db["anime"].insert_one({
        "_id": "anime_new_day",
        "title": {"english": "New Day Anime"},
        "status": "upcoming",
        "release_date": {"year": 2026, "month": 3, "day": 15, "precision": "day"},
        "year": 2026,
        "season": "Spring",
        "is_deleted": False
    })
    
    # Dated releases should include day precision but exclude month/legacy precision
    dated = await get_dated_releases_range("2026-03-01", "2026-03-31")
    dated_ids = [r["content_id"] for r in dated]
    assert "anime_new_day" in dated_ids
    assert "anime_new_month" not in dated_ids
    assert "anime_legacy" not in dated_ids

    # Announced releases should include month precision
    announced = await get_announced_releases_range("2026-03-01", "2026-03-31")
    announced_ids = [r["content_id"] for r in announced]
    assert "anime_new_month" in announced_ids
    assert "anime_new_day" not in announced_ids
    assert "anime_legacy" not in announced_ids
