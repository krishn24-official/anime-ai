import pytest
from app.services.movie_admin_service import create_movie
from app.repositories import movie_repository, content_repository
from app.db.mongo import get_db

@pytest.mark.asyncio
async def test_create_movie_released_needs_day():
    with pytest.raises(ValueError, match="released movie must have day precision"):
        await create_movie(
            admin_id="admin_123",
            title="Test Movie",
            original_title=None,
            released=True,
            sub_status="Released",
            day=None,
            month=5,
            year=2024,
            precision="month",
            runtime_minutes=120,
            genres=[],
            director=[],
            writers=[],
            producers=[],
            production_house=[],
            actors=[],
            plot=None,
            language=[],
            country=[],
            tagline=None,
            trailers=[],
            cast=[],
            poster_bytes=None,
            backdrop_bytes=None
        )

@pytest.mark.asyncio
async def test_create_movie_not_released_month():
    db = get_db()
    content_id = await create_movie(
        admin_id="admin_123",
        title="Test Movie 2",
        original_title=None,
        released=False,
        sub_status="Post Production",
        day=None,
        month=5,
        year=2024,
        precision="month",
        runtime_minutes=120,
        genres=[],
        director=[],
        writers=[],
        producers=[],
        production_house=[],
        actors=[],
        plot=None,
        language=[],
        country=[],
        tagline=None,
        trailers=[],
        cast=[],
        poster_bytes=None,
        backdrop_bytes=None
    )
    
    movie = await db["movies"].find_one({"_id": content_id})
    assert movie["status"] == "Post Production"
    assert movie["release_date"] is None
    assert movie["release_precision"] == {"year": 2024, "month": 5, "day": None, "precision": "month"}
    assert movie["year"] == 2024

@pytest.mark.asyncio
async def test_create_movie_duplicate_slug():
    db = get_db()
    await db["movies"].insert_one({"_id": "movie_duplicate", "title": "Duplicate"})
    
    with pytest.raises(ValueError, match="already exists"):
        await create_movie(
            admin_id="admin_123",
            title="Duplicate",
            original_title=None,
            released=False,
            sub_status="Planned",
            day=None,
            month=None,
            year=2025,
            precision="year",
            runtime_minutes=None,
            genres=[],
            director=[],
            writers=[],
            producers=[],
            production_house=[],
            actors=[],
            plot=None,
            language=[],
            country=[],
            tagline=None,
            trailers=[],
            cast=[],
            poster_bytes=None,
            backdrop_bytes=None
        )

@pytest.mark.asyncio
async def test_get_upcoming_estimated_merges():
    db = get_db()
    
    # 1 anime
    await db["anime"].insert_one({
        "_id": "anime_1",
        "title": {"english": "Anime 1"},
        "status": "upcoming",
        "year": 2025,
        "season": "Winter"
    })
    
    # 1 movie
    await db["movies"].insert_one({
        "_id": "movie_1",
        "title": "Movie 1",
        "status": "Planned",
        "release_date": None,
        "release_precision": {"year": 2024, "month": 5, "day": None, "precision": "month"}
    })
    
    # 1 tv series
    await db["tv_series"].insert_one({
        "_id": "tv_1",
        "title": "TV 1",
        "status": "Planned",
        "first_air_date": None,
        "release_precision": {"year": 2026, "month": None, "day": None, "precision": "year"}
    })
    
    results = await content_repository.get_upcoming_estimated(limit=10)
    
    assert len(results) == 3
    
    # Check ordering by sort_year, sort_month
    assert results[0]["content_id"] == "movie_1" # 2024
    assert results[1]["content_id"] == "anime_1" # 2025
    assert results[2]["content_id"] == "tv_1" # 2026
    
    assert results[0]["season_label"] == "May 2024"
    assert results[1]["season_label"] == "Winter 2025"
    assert results[2]["season_label"] == "2026"

@pytest.mark.asyncio
async def test_get_upcoming_dated_excludes_coarse():
    db = get_db()
    await db["movies"].insert_one({
        "_id": "movie_2",
        "title": "Movie 2",
        "status": "Planned",
        "release_date": None,
        "release_precision": {"year": 2024, "month": 5, "day": None, "precision": "month"}
    })
    
    results = await content_repository.get_upcoming_dated(limit=10)
    assert len(results) == 0
