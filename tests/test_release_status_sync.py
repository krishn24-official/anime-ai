import pytest
from datetime import datetime, timezone, date
from dateutil.relativedelta import relativedelta
from app.db.mongo import get_db
from app.services.release_status_sync import sync_anime_release_status, sync_movie_release_status, sync_all_release_statuses

@pytest.mark.asyncio
async def test_sync_anime_release_status_auto_releases():
    db = get_db()
    today = datetime.now(timezone.utc).date()
    past_date = today - relativedelta(days=5)
    
    await db["anime"].insert_one({
        "_id": "anime_past",
        "status": "upcoming",
        "release_date": {
            "year": past_date.year,
            "month": past_date.month,
            "day": past_date.day,
            "precision": "day"
        }
    })
    
    summary = await sync_anime_release_status()
    assert summary["auto_released"] == 1
    assert summary["flagged_for_review"] == 0
    
    doc = await db["anime"].find_one({"_id": "anime_past"})
    assert doc["status"] == "ongoing"
    assert doc.get("needs_release_review") is False

@pytest.mark.asyncio
async def test_sync_anime_release_status_flags_month():
    db = get_db()
    today = datetime.now(timezone.utc).date()
    past_month = today - relativedelta(months=2)
    
    await db["anime"].insert_one({
        "_id": "anime_month_past",
        "status": "upcoming",
        "release_date": {
            "year": past_month.year,
            "month": past_month.month,
            "day": None,
            "precision": "month"
        }
    })
    
    summary = await sync_anime_release_status()
    assert summary["auto_released"] == 0
    assert summary["flagged_for_review"] == 1
    
    doc = await db["anime"].find_one({"_id": "anime_month_past"})
    assert doc["status"] == "upcoming"
    assert doc.get("needs_release_review") is True

@pytest.mark.asyncio
async def test_sync_anime_release_status_ignores_future():
    db = get_db()
    today = datetime.now(timezone.utc).date()
    future_date = today + relativedelta(days=5)
    
    await db["anime"].insert_one({
        "_id": "anime_future",
        "status": "upcoming",
        "release_date": {
            "year": future_date.year,
            "month": future_date.month,
            "day": future_date.day,
            "precision": "day"
        }
    })
    
    summary = await sync_anime_release_status()
    assert summary["auto_released"] == 0
    assert summary["flagged_for_review"] == 0
    
    doc = await db["anime"].find_one({"_id": "anime_future"})
    assert doc["status"] == "upcoming"

@pytest.mark.asyncio
async def test_sync_movie_release_status_auto_releases():
    db = get_db()
    today = datetime.now(timezone.utc).date()
    past_date = today - relativedelta(days=5)
    past_str = past_date.strftime("%Y-%m-%d")
    
    await db["movies"].insert_one({
        "_id": "movie_past",
        "status": "Planned",
        "release_date": past_str,
        "release_precision": None
    })
    
    summary = await sync_movie_release_status()
    assert summary["auto_released"] == 1
    assert summary["flagged_for_review"] == 0
    
    doc = await db["movies"].find_one({"_id": "movie_past"})
    assert doc["status"] == "Released"
    assert doc.get("needs_release_review") is False

@pytest.mark.asyncio
async def test_sync_movie_release_status_flags_month():
    db = get_db()
    today = datetime.now(timezone.utc).date()
    past_month = today - relativedelta(months=2)
    
    await db["movies"].insert_one({
        "_id": "movie_month_past",
        "status": "Post Production",
        "release_date": None,
        "release_precision": {
            "year": past_month.year,
            "month": past_month.month,
            "day": None,
            "precision": "month"
        }
    })
    
    summary = await sync_movie_release_status()
    assert summary["auto_released"] == 0
    assert summary["flagged_for_review"] == 1
    
    doc = await db["movies"].find_one({"_id": "movie_month_past"})
    assert doc["status"] == "Post Production"
    assert doc.get("needs_release_review") is True

@pytest.mark.asyncio
async def test_sync_movie_release_status_ignores_future():
    db = get_db()
    today = datetime.now(timezone.utc).date()
    future_date = today + relativedelta(days=5)
    future_str = future_date.strftime("%Y-%m-%d")
    
    await db["movies"].insert_one({
        "_id": "movie_future",
        "status": "In Production",
        "release_date": future_str,
        "release_precision": None
    })
    
    summary = await sync_movie_release_status()
    assert summary["auto_released"] == 0
    assert summary["flagged_for_review"] == 0
    
    doc = await db["movies"].find_one({"_id": "movie_future"})
    assert doc["status"] == "In Production"

@pytest.mark.asyncio
async def test_sync_all_release_statuses():
    db = get_db()
    # Setup some dummy data
    today = datetime.now(timezone.utc).date()
    past_date = today - relativedelta(days=5)
    past_str = past_date.strftime("%Y-%m-%d")
    
    await db["movies"].insert_one({
        "_id": "movie_all_test",
        "status": "Planned",
        "release_date": past_str,
        "release_precision": None
    })
    
    res = await sync_all_release_statuses()
    
    assert res["movies"]["auto_released"] == 1
    assert res["total_auto_released"] >= 1
