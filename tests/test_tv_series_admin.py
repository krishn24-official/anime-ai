import pytest
from app.services.tv_series_admin_service import create_tv_series, update_tv_series, delete_tv_series
from app.services.release_status_sync import sync_tv_series_release_status
from app.db.mongo import get_db
import datetime

@pytest.mark.asyncio
async def test_create_tv_series_released_requires_day():
    with pytest.raises(ValueError, match="must have day precision"):
        await create_tv_series(
            admin_id="admin_123",
            title="Released TV",
            original_title=None,
            released=True,
            status_value="Returning Series",
            start_day=None,
            start_month=4,
            start_year=2024,
            start_precision="month",
            end_day=None,
            end_month=None,
            end_year=None,
            end_precision=None,
            total_seasons=1,
            total_episodes=12,
            episode_runtime_minutes=24,
            genres=[],
            creators=[],
            producers=[],
            production_house=[],
            actors=[],
            plot="",
            language=[],
            country=[],
            tagline="",
            trailers=[],
            cast=[],
            poster_bytes=None,
            backdrop_bytes=None
        )

@pytest.mark.asyncio
async def test_create_tv_series_not_released_month_precision():
    db = get_db()
    await db["tv_series"].delete_many({"_id": "tv_not_released_tv"})
    
    content_id = await create_tv_series(
        admin_id="admin_123",
        title="Not Released TV",
        original_title=None,
        released=False,
        status_value="Planned",
        start_day=None,
        start_month=5,
        start_year=2025,
        start_precision="month",
        end_day=None,
        end_month=None,
        end_year=None,
        end_precision=None,
        total_seasons=None,
        total_episodes=None,
        episode_runtime_minutes=None,
        genres=[],
        creators=[],
        producers=[],
        production_house=[],
        actors=[],
        plot="",
        language=[],
        country=[],
        tagline="",
        trailers=[],
        cast=[],
        poster_bytes=None,
        backdrop_bytes=None
    )
    
    doc = await db["tv_series"].find_one({"_id": content_id})
    assert doc["first_air_date"] is None
    assert doc["first_air_precision"]["year"] == 2025
    assert doc["first_air_precision"]["month"] == 5
    assert doc["first_air_precision"]["precision"] == "month"
    assert doc["status"] == "Planned"
    assert doc["needs_release_review"] is False

@pytest.mark.asyncio
async def test_create_tv_series_invalid_end_date():
    with pytest.raises(ValueError, match="end_date cannot be before the start release_date"):
        await create_tv_series(
            admin_id="admin_123",
            title="Invalid End TV",
            original_title=None,
            released=True,
            status_value="Returning Series",
            start_day=1,
            start_month=1,
            start_year=2020,
            start_precision="day",
            end_day=1,
            end_month=1,
            end_year=2019,
            end_precision="day",
            total_seasons=None,
            total_episodes=None,
            episode_runtime_minutes=None,
            genres=[],
            creators=[],
            producers=[],
            production_house=[],
            actors=[],
            plot="",
            language=[],
            country=[],
            tagline="",
            trailers=[],
            cast=[],
            poster_bytes=None,
            backdrop_bytes=None
        )

@pytest.mark.asyncio
async def test_duplicate_slug_protection():
    db = get_db()
    await db["tv_series"].delete_many({"_id": "tv_dup_tv"})
    
    await create_tv_series(
        admin_id="admin_123",
        title="Dup TV",
        original_title=None,
        released=False,
        status_value="Planned",
        start_day=None,
        start_month=None,
        start_year=2026,
        start_precision="year",
        end_day=None,
        end_month=None,
        end_year=None,
        end_precision=None,
        total_seasons=None,
        total_episodes=None,
        episode_runtime_minutes=None,
        genres=[],
        creators=[],
        producers=[],
        production_house=[],
        actors=[],
        plot="",
        language=[],
        country=[],
        tagline="",
        trailers=[],
        cast=[],
        poster_bytes=None,
        backdrop_bytes=None
    )
    
    # Second create should fail
    with pytest.raises(ValueError, match="already exists"):
        await create_tv_series(
            admin_id="admin_123",
            title="Dup TV",
            original_title=None,
            released=False,
            status_value="Planned",
            start_day=None,
            start_month=None,
            start_year=2026,
            start_precision="year",
            end_day=None,
            end_month=None,
            end_year=None,
            end_precision=None,
            total_seasons=None,
            total_episodes=None,
            episode_runtime_minutes=None,
            genres=[],
            creators=[],
            plot="",
            language=[],
            country=[],
            tagline="",
            trailers=[],
            poster_bytes=None,
            backdrop_bytes=None
        )
        
    await delete_tv_series("tv_dup_tv")
    
    # Soft deleted should still fail
    with pytest.raises(ValueError, match="already exists"):
        await create_tv_series(
            admin_id="admin_123",
            title="Dup TV",
            original_title=None,
            released=False,
            status_value="Planned",
            start_day=None,
            start_month=None,
            start_year=2026,
            start_precision="year",
            end_day=None,
            end_month=None,
            end_year=None,
            end_precision=None,
            total_seasons=None,
            total_episodes=None,
            episode_runtime_minutes=None,
            genres=[],
            creators=[],
            plot="",
            language=[],
            country=[],
            tagline="",
            trailers=[],
            poster_bytes=None,
            backdrop_bytes=None
        )

@pytest.mark.asyncio
async def test_update_tv_series_clear_end_date():
    db = get_db()
    await db["tv_series"].delete_many({"_id": "tv_clear_end_tv"})
    
    content_id = await create_tv_series(
        admin_id="admin_123",
        title="Clear End TV",
        original_title=None,
        released=True,
        status_value="Ended",
        start_day=1,
        start_month=1,
        start_year=2020,
        start_precision="day",
        end_day=1,
        end_month=1,
        end_year=2022,
        end_precision="day",
        total_seasons=None,
        total_episodes=None,
        episode_runtime_minutes=None,
        genres=[],
        creators=[],
        producers=[],
        production_house=[],
        actors=[],
        plot="",
        language=[],
        country=[],
        tagline="",
        trailers=[],
        cast=[],
        poster_bytes=None,
        backdrop_bytes=None
    )
    
    # Update to clear end date
    await update_tv_series(
        admin_id="admin_123",
        content_id=content_id,
        clear_end_date=True
    )
    
    doc = await db["tv_series"].find_one({"_id": content_id})
    assert doc["last_air_date"] is None
    assert doc["last_air_precision"] is None
    
    # Update without clear_end_date and without end fields leaves it untouched
    await update_tv_series(
        admin_id="admin_123",
        content_id=content_id,
        end_day=1,
        end_month=1,
        end_year=2023,
        end_precision="day"
    )
    
    doc = await db["tv_series"].find_one({"_id": content_id})
    assert doc["last_air_date"] == "2023-01-01"
    
    await update_tv_series(
        admin_id="admin_123",
        content_id=content_id,
        title="Updated Title"
    )
    
    doc = await db["tv_series"].find_one({"_id": content_id})
    assert doc["last_air_date"] == "2023-01-01"

@pytest.mark.asyncio
async def test_sync_tv_series_release_status():
    db = get_db()
    today = datetime.datetime.now(datetime.timezone.utc).date()
    today_str = today.strftime("%Y-%m-%d")
    
    past_month = today.month - 1
    past_year = today.year
    if past_month == 0:
        past_month = 12
        past_year -= 1
        
    await db["tv_series"].delete_many({"_id": {"$in": ["tv_sync_day_tv", "tv_sync_month_tv"]}})
    
    await db["tv_series"].insert_many([
        {
            "_id": "tv_sync_day_tv",
            "title": "Sync Day TV",
            "status": "Planned",
            "first_air_date": "2020-01-01",
            "first_air_precision": None,
            "is_deleted": False,
            "needs_release_review": False
        },
        {
            "_id": "tv_sync_month_tv",
            "title": "Sync Month TV",
            "status": "In Production",
            "first_air_date": None,
            "first_air_precision": {
                "year": past_year,
                "month": past_month,
                "precision": "month"
            },
            "is_deleted": False,
            "needs_release_review": False
        }
    ])
    
    stats = await sync_tv_series_release_status()
    
    assert stats["auto_released"] >= 1
    assert stats["flagged_for_review"] >= 1
    
    day_doc = await db["tv_series"].find_one({"_id": "tv_sync_day_tv"})
    assert day_doc["status"] == "Returning Series"
    assert day_doc["needs_release_review"] is False
    
    month_doc = await db["tv_series"].find_one({"_id": "tv_sync_month_tv"})
    assert month_doc["status"] == "In Production"
    assert month_doc["needs_release_review"] is True
