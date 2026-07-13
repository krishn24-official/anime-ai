import pytest
from app.services.episode_admin_service import create_episode
from app.db.mongo import get_db
from bson import ObjectId

@pytest.fixture(autouse=True)
async def cleanup_db():
    db = get_db()
    await db["anime"].delete_many({"_id": ObjectId("60c72b2f9b1d8b5a5198e3b1")})
    await db["anime"].delete_many({"_id": ObjectId("60c72b2f9b1d8b5a5198e3b2")})
    await db["tv_series"].delete_many({"_id": "test_tv_1"})
    await db["episodes"].delete_many({"anime_id": {"$in": ["60c72b2f9b1d8b5a5198e3b1", "60c72b2f9b1d8b5a5198e3b2"]}})
    await db["episodes"].delete_many({"tv_series_id": "test_tv_1"})
    
    await db["anime"].insert_one({"_id": ObjectId("60c72b2f9b1d8b5a5198e3b1"), "title": {"english": "Test Anime 1"}, "is_deleted": False})
    await db["anime"].insert_one({"_id": ObjectId("60c72b2f9b1d8b5a5198e3b2"), "title": {"english": "Test Anime 2"}, "is_deleted": False})
    await db["tv_series"].insert_one({"_id": "test_tv_1", "title": "Test TV 1", "is_deleted": False})
    
    yield
    
    await db["anime"].delete_many({"_id": ObjectId("60c72b2f9b1d8b5a5198e3b1")})
    await db["anime"].delete_many({"_id": ObjectId("60c72b2f9b1d8b5a5198e3b2")})
    await db["tv_series"].delete_many({"_id": "test_tv_1"})
    await db["episodes"].delete_many({"anime_id": {"$in": ["60c72b2f9b1d8b5a5198e3b1", "60c72b2f9b1d8b5a5198e3b2"]}})
    await db["episodes"].delete_many({"tv_series_id": "test_tv_1"})

@pytest.mark.asyncio
async def test_create_episode_validation():
    # Invalid parent_type
    with pytest.raises(ValueError, match="parent_type must be either"):
        await create_episode("admin_1", "invalid_type", "60c72b2f9b1d8b5a5198e3b1", 1)
        
    # Non-existent parent
    with pytest.raises(ValueError, match="not found"):
        await create_episode("admin_1", "anime", "60c72b2f9b1d8b5a5198e3b4", 1)
        
    # Invalid release date
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        await create_episode("admin_1", "anime", "60c72b2f9b1d8b5a5198e3b1", 1, release_date="2026-1-1")

@pytest.mark.asyncio
async def test_create_episode_duplicate_logic():
    # Create ep 1 for anime 1
    await create_episode("admin_1", "anime", "60c72b2f9b1d8b5a5198e3b1", 1, title="Ep 1")
    
    # Create ep 1 for anime 2 (should succeed, different parent)
    await create_episode("admin_1", "anime", "60c72b2f9b1d8b5a5198e3b2", 1, title="Ep 1 Diff")
    
    # Create ep 1 for tv_series 1 (should succeed, different parent)
    await create_episode("admin_1", "tv_series", "test_tv_1", 1, title="Ep 1 TV")
    
    # Attempt duplicate for anime 1
    with pytest.raises(ValueError, match="already exists"):
        await create_episode("admin_1", "anime", "60c72b2f9b1d8b5a5198e3b1", 1, title="Duplicate")

@pytest.mark.asyncio
async def test_create_episode_parent_id_assignment():
    ep_anime = await create_episode("admin_1", "anime", "60c72b2f9b1d8b5a5198e3b1", 2)
    assert ep_anime["anime_id"] == "60c72b2f9b1d8b5a5198e3b1"
    assert ep_anime["tv_series_id"] is None
    
    ep_tv = await create_episode("admin_1", "tv_series", "test_tv_1", 2)
    assert ep_tv["anime_id"] is None
    assert ep_tv["tv_series_id"] == "test_tv_1"
