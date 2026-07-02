import pytest
import time
from app.db.mongo import get_db
from app.repositories.chat_repository import find_character, _char_cache

@pytest.fixture(autouse=True)
async def seed_chat_test_data():
    db = get_db()
    await db["characters"].delete_many({})
    _char_cache.clear()
    
    await db["characters"].insert_many([
        {
            "_id": "char_naruto",
            "name": "Naruto Uzumaki",
            "is_deleted": False
        },
        {
            "_id": "char_boruto",
            "name": "Boruto Uzumaki",
            "is_deleted": False
        },
        {
            "_id": "char_sasuke",
            "name": "Sasuke Uchiha",
            "is_deleted": False
        }
    ])

@pytest.mark.anyio
async def test_find_character_prioritized():
    # 1. Exact match
    char = await find_character("Naruto Uzumaki")
    assert char is not None
    assert char["_id"] == "char_naruto"

    # 2. Starts-with match
    char = await find_character("Boruto")
    assert char is not None
    assert char["_id"] == "char_boruto"

    # 3. Contains match
    char = await find_character("Uchiha")
    assert char is not None
    assert char["_id"] == "char_sasuke"

    # 4. Not found
    char = await find_character("Goku")
    assert char is None

@pytest.mark.anyio
async def test_find_character_caching():
    # Query to populate cache
    char1 = await find_character("Naruto Uzumaki")
    assert char1 is not None

    # Check cache entry
    assert "naruto uzumaki" in _char_cache
    cached_doc, cached_time = _char_cache["naruto uzumaki"]
    assert cached_doc["_id"] == "char_naruto"
    
    # Modify DB directly
    db = get_db()
    await db["characters"].update_one({"_id": "char_naruto"}, {"$set": {"name": "Naruto Namikaze"}})
    
    # Retrieve again, should hit the cache and return the old name
    char2 = await find_character("Naruto Uzumaki")
    assert char2 is not None
    assert char2["name"] == "Naruto Uzumaki"
