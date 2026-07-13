import pytest
from app.services.chapter_admin_service import create_chapter
from app.db.mongo import get_db

@pytest.fixture(autouse=True)
async def cleanup_db():
    db = get_db()
    await db["manga"].delete_many({"_id": "test_manga_1"})
    await db["manga"].delete_many({"_id": "test_manga_2"})
    await db["chapters"].delete_many({"manga_id": {"$in": ["test_manga_1", "test_manga_2"]}})
    
    await db["manga"].insert_one({"_id": "test_manga_1", "name": "Test Manga 1", "is_deleted": False})
    await db["manga"].insert_one({"_id": "test_manga_2", "name": "Test Manga 2", "is_deleted": False})
    
    yield
    
    await db["manga"].delete_many({"_id": "test_manga_1"})
    await db["manga"].delete_many({"_id": "test_manga_2"})
    await db["chapters"].delete_many({"manga_id": {"$in": ["test_manga_1", "test_manga_2"]}})

@pytest.mark.asyncio
async def test_create_chapter_validation():
    # Non-existent parent
    with pytest.raises(ValueError, match="not found"):
        await create_chapter("admin_1", "does_not_exist", 1)
        
    # Invalid release date
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        await create_chapter("admin_1", "test_manga_1", 1, release_date="2026-1-1")

@pytest.mark.asyncio
async def test_create_chapter_duplicate_logic():
    # Create ch 1 for manga 1
    await create_chapter("admin_1", "test_manga_1", 1)
    
    # Create ch 1 for manga 2 (should succeed, different parent)
    await create_chapter("admin_1", "test_manga_2", 1)
    
    # Attempt duplicate for manga 1
    with pytest.raises(ValueError, match="already exists"):
        await create_chapter("admin_1", "test_manga_1", 1)
