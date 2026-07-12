import pytest
from datetime import datetime
from app.db.mongo import get_db
from app.repositories.content_repository import get_dated_releases_range, get_announced_releases_range

@pytest.mark.asyncio
async def test_get_dated_releases_range():
    db = get_db()
    
    start_date = "2026-06-01"
    end_date = "2026-06-30"
    
    await db["movies"].insert_many([
        {
            "_id": "movie_in_range",
            "title": "Movie In Range",
            "release_date": "2026-06-15"
        },
        {
            "_id": "movie_out_range",
            "title": "Movie Out Range",
            "release_date": "2026-07-01"
        }
    ])
    
    await db["tv_series"].insert_many([
        {
            "_id": "tv_start",
            "title": "TV Start",
            "first_air_date": "2026-06-10"
        },
        {
            "_id": "tv_end",
            "title": "TV End",
            "last_air_date": "2026-06-20"
        }
    ])
    
    await db["anime"].insert_many([
        {
            "_id": "anime_start",
            "title": {"english": "Anime Start"},
            "release_date": {"year": 2026, "month": 6, "day": 5, "precision": "day"}
        },
        {
            "_id": "anime_end",
            "title": {"english": "Anime End"},
            "end_date": {"year": 2026, "month": 6, "day": 25, "precision": "day"}
        },
        {
            "_id": "anime_month_precision",
            "title": {"english": "Anime Month Precision"},
            "release_date": {"year": 2026, "month": 6, "precision": "month"}
        }
    ])
    
    results = await get_dated_releases_range(start_date, end_date)
    
    assert len(results) == 5
    
    ids = [(r["content_id"], r["event_type"]) for r in results]
    assert ("anime_start", "release_start") in ids
    assert ("tv_start", "release_start") in ids
    assert ("movie_in_range", "release_start") in ids
    assert ("tv_end", "release_end") in ids
    assert ("anime_end", "release_end") in ids
    
    # ensure month precision anime is not in dated releases
    assert "anime_month_precision" not in [r["content_id"] for r in results]


@pytest.mark.asyncio
async def test_get_announced_releases_range():
    db = get_db()
    
    start_date = "2026-06-01"
    end_date = "2026-12-31"
    
    await db["movies"].insert_many([
        {
            "_id": "movie_month",
            "title": "Movie Month",
            "release_precision": {"year": 2026, "month": 6, "precision": "month"}
        },
        {
            "_id": "movie_year",
            "title": "Movie Year",
            "release_precision": {"year": 2026, "precision": "year"}
        }
    ])
    
    await db["tv_series"].insert_many([
        {
            "_id": "tv_month",
            "title": "TV Month",
            "first_air_precision": {"year": 2026, "month": 7, "precision": "month"}
        }
    ])
    
    await db["anime"].insert_many([
        {
            "_id": "anime_year",
            "title": {"english": "Anime Year"},
            "release_date": {"year": 2026, "precision": "year"}
        },
        {
            "_id": "anime_out_range",
            "title": {"english": "Anime Out Range"},
            "release_date": {"year": 2025, "precision": "year"}
        }
    ])
    
    results = await get_announced_releases_range(start_date, end_date)
    
    assert len(results) == 4
    
    # 2026-06-30 (last day of june)
    assert results[0]["content_id"] == "movie_month"
    assert results[0]["pinned_date"] == "2026-06-30"
    assert results[0]["label"] == "June 2026"
    
    # 2026-07-31 (last day of july)
    assert results[1]["content_id"] == "tv_month"
    assert results[1]["pinned_date"] == "2026-07-31"
    assert results[1]["label"] == "July 2026"
    
    # 2026-12-31
    year_ids = [results[2]["content_id"], results[3]["content_id"]]
    assert set(year_ids) == {"movie_year", "anime_year"}
    assert results[2]["pinned_date"] == "2026-12-31"
    assert results[3]["pinned_date"] == "2026-12-31"
    
    # out of range anime should be excluded
    assert "anime_out_range" not in [r["content_id"] for r in results]
