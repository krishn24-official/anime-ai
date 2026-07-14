import pytest
from app.services.character_admin_service import create_character, delete_character
from app.repositories import character_admin_repository
from app.db.mongo import get_db

@pytest.fixture
async def character_db_setup():
    db = get_db()
    # Insert a dummy anime and manga for testing relations
    await db["anime"].insert_one({"_id": "anime_test_1", "title": {"english": "Test Anime"}, "is_deleted": False})
    await db["manga"].insert_one({"_id": "manga_test_1", "name": "Test Manga", "is_deleted": False})
    
    yield
    
    await db["anime"].delete_many({"_id": "anime_test_1"})
    await db["manga"].delete_many({"_id": "manga_test_1"})
    await db["characters"].delete_many({"_id": {"$regex": "^char_test"}})

@pytest.mark.asyncio
async def test_create_character_minimal(character_db_setup):
    db = get_db()
    
    # Clean up before
    await db["characters"].delete_many({"_id": "char_test_minimal"})
    
    content_id = await create_character(
        admin_id="admin_123",
        name="Test Minimal",
        native_name=None,
        birth_day=None,
        birth_month=None,
        height=None,
        hair_color=None,
        has_hair=None,
        description=None,
        anime_ids=[],
        manga_ids=[],
        affiliations=[],
        abilities=[],
        forms=[],
        status="",
        species="",
        gender=None,
        role="",
        tags=[],
        profile_bytes=None,
        banner_bytes=None
    )
    
    assert content_id == "char_test_minimal"
    
    doc = await db["characters"].find_one({"_id": content_id})
    assert doc is not None
    assert doc["name"] == "Test Minimal"
    assert doc["status"] == "unknown"
    assert doc["species"] == "unknown"
    assert doc["role"] == "unknown"
    assert doc["source_metadata"]["source"] == "manual"
    
    # Clean up after
    await db["characters"].delete_many({"_id": "char_test_minimal"})

@pytest.mark.asyncio
async def test_create_character_duplicate_slug(character_db_setup):
    db = get_db()
    
    # Ensure existing
    await db["characters"].insert_one({
        "_id": "char_test_duplicate",
        "name": "Test Duplicate",
        "is_deleted": False
    })
    
    with pytest.raises(ValueError) as excinfo:
        await create_character(
            admin_id="admin_123",
            name="Test Duplicate",
            native_name=None,
            birth_day=None,
            birth_month=None,
            height=None,
            hair_color=None,
            has_hair=None,
            description=None,
            anime_ids=[],
            manga_ids=[],
            affiliations=[],
            abilities=[],
            forms=[],
            status="",
            species="",
            gender=None,
            role="",
            tags=[],
            profile_bytes=None,
            banner_bytes=None
        )
        
    assert "already exists" in str(excinfo.value)
    
    # Clean up
    await db["characters"].delete_many({"_id": "char_test_duplicate"})

@pytest.mark.asyncio
async def test_create_character_invalid_relations(character_db_setup):
    with pytest.raises(ValueError) as excinfo:
        await create_character(
            admin_id="admin_123",
            name="Test Invalid Rel",
            native_name=None,
            birth_day=None,
            birth_month=None,
            height=None,
            hair_color=None,
            has_hair=None,
            description=None,
            anime_ids=["anime_does_not_exist"],
            manga_ids=[],
            affiliations=[],
            abilities=[],
            forms=[],
            status="",
            species="",
            gender=None,
            role="",
            tags=[],
            profile_bytes=None,
            banner_bytes=None
        )
        
    assert "Anime IDs not found" in str(excinfo.value)

@pytest.mark.asyncio
async def test_soft_delete_character(character_db_setup):
    db = get_db()
    
    await db["characters"].insert_one({
        "_id": "char_test_delete",
        "name": "Test Delete",
        "is_deleted": False,
        "deleted_at": None
    })
    
    await delete_character("char_test_delete")
    
    doc = await db["characters"].find_one({"_id": "char_test_delete"})
    assert doc is not None
    assert doc["is_deleted"] is True
    assert doc["deleted_at"] is not None
    
    # Verify that trying to create a character with the same name after soft delete still raises ValueError
    with pytest.raises(ValueError) as excinfo:
        await create_character(
            admin_id="admin_123",
            name="Test Delete",
            native_name=None,
            birth_day=None,
            birth_month=None,
            height=None,
            hair_color=None,
            has_hair=None,
            description=None,
            anime_ids=[],
            manga_ids=[],
            affiliations=[],
            abilities=[],
            forms=[],
            status="",
            species="",
            gender=None,
            role="",
            tags=[],
            profile_bytes=None,
            banner_bytes=None
        )
        
    assert "already exists" in str(excinfo.value)
    
    # Clean up
    await db["characters"].delete_many({"_id": "char_test_delete"})
