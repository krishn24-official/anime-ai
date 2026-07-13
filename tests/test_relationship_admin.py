import pytest
from app.services.relationship_admin_service import create_relationship, check_relationship_exists, _make_rel_id, resolve_entity_type
from app.repositories.relationship_repository import search_relationship_entities
from app.db.mongo import get_db

@pytest.mark.asyncio
async def test_create_relationship_invalid_type():
    with pytest.raises(ValueError, match="Invalid relationship type"):
        await create_relationship("admin123", "char_1", "char_2", "friend", "not_a_type", None, None)

@pytest.mark.asyncio
async def test_create_relationship_same_target():
    with pytest.raises(ValueError, match="source_id and target_id cannot be the same"):
        await create_relationship("admin123", "char_1", "char_1", "friend", "friendship", None, None)

@pytest.mark.asyncio
async def test_create_relationship_entity_not_found(db_setup):
    # db is provided by some fixture, but we can just use real test db or mock
    # since we don't know the fixtures, let's mock the DB or just rely on existing test setup.
    # The existing codebase likely has a pytest setup that drops DB.
    db = get_db()
    await db["characters"].delete_many({})
    await db["organizations"].delete_many({})
    
    with pytest.raises(ValueError, match="Source entity char_1 not found"):
        await create_relationship("admin123", "char_1", "char_2", "friend", "friendship", None, None)

@pytest.mark.asyncio
async def test_create_relationship_duplicate_check(db_setup):
    db = get_db()
    # Insert test entities
    await db["characters"].insert_many([
        {"_id": "char_test_a", "is_deleted": False},
        {"_id": "char_test_b", "is_deleted": False}
    ])
    
    # First create
    res1 = await create_relationship("admin", "char_test_a", "char_test_b", "rival", "combat", "none", None)
    assert res1["status"] == "created"
    assert len(res1["docs"]) == 2
    
    # Duplicate without overwrite
    res2 = await create_relationship("admin", "char_test_a", "char_test_b", "rival", "combat", "different context", None, overwrite=False)
    assert res2["status"] == "duplicate"
    
    # Duplicate with overwrite
    res3 = await create_relationship("admin", "char_test_a", "char_test_b", "rival", "combat", "updated context", None, overwrite=True)
    assert res3["status"] == "overwritten"
    
    # Verify DB state
    rel_id = _make_rel_id("char_test_a", "char_test_b", "rival")
    doc = await db["relationships"].find_one({"_id": rel_id})
    assert doc["context"] == "updated context"
    
    # Clean up
    await db["characters"].delete_many({"_id": {"$in": ["char_test_a", "char_test_b"]}})
    await db["relationships"].delete_many({"source_id": {"$in": ["char_test_a", "char_test_b"]}})


@pytest.mark.asyncio
async def test_resolve_entity_type(db_setup):
    db = get_db()
    # Insert dummy records across 6 collections
    await db["characters"].insert_one({"_id": "char_99", "is_deleted": False})
    await db["organizations"].insert_one({"_id": "org_99", "is_deleted": False})
    await db["anime"].insert_one({"_id": "anime_99", "is_deleted": False})
    await db["manga"].insert_one({"_id": "manga_99", "is_deleted": False})
    await db["movies"].insert_one({"_id": "movie_99", "is_deleted": False})
    await db["tv_series"].insert_one({"_id": "tv_99", "is_deleted": False})
    
    assert await resolve_entity_type("char_99") == "character"
    assert await resolve_entity_type("org_99") == "organization"
    assert await resolve_entity_type("anime_99") == "anime"
    assert await resolve_entity_type("manga_99") == "manga"
    assert await resolve_entity_type("movie_99") == "movie"
    assert await resolve_entity_type("tv_99") == "tv_series"
    
    # Test not found
    assert await resolve_entity_type("char_999") is None
    
    # Test soft-deleted
    await db["characters"].insert_one({"_id": "char_del", "is_deleted": True})
    assert await resolve_entity_type("char_del") is None
    
    # Test invalid prefix
    assert await resolve_entity_type("unknown_123") is None
    
    # Clean up
    await db["characters"].delete_many({"_id": {"$in": ["char_99", "char_del"]}})
    await db["organizations"].delete_many({"_id": "org_99"})
    await db["anime"].delete_many({"_id": "anime_99"})
    await db["manga"].delete_many({"_id": "manga_99"})
    await db["movies"].delete_many({"_id": "movie_99"})
    await db["tv_series"].delete_many({"_id": "tv_99"})


@pytest.mark.asyncio
async def test_create_appears_in_relationship(db_setup):
    db = get_db()
    await db["characters"].insert_one({"_id": "char_99", "is_deleted": False})
    await db["anime"].insert_one({"_id": "anime_99", "is_deleted": False})
    
    res = await create_relationship(
        "admin", "char_99", "anime_99", "appears_in", "media", None, None
    )
    assert res["status"] == "created"
    
    rel_id = _make_rel_id("char_99", "anime_99", "appears_in")
    inv_id = _make_rel_id("anime_99", "char_99", "features")
    
    doc1 = await db["relationships"].find_one({"_id": rel_id})
    doc2 = await db["relationships"].find_one({"_id": inv_id})
    
    assert doc1 is not None
    assert doc2 is not None
    assert doc1["relationship"] == "appears_in"
    assert doc2["relationship"] == "features"
    
    # Clean up
    await db["characters"].delete_many({"_id": "char_99"})
    await db["anime"].delete_many({"_id": "anime_99"})
    await db["relationships"].delete_many({"_id": {"$in": [rel_id, inv_id]}})


@pytest.mark.asyncio
async def test_search_relationship_entities_cross_collection(db_setup):
    db = get_db()
    # Insert a character and an anime with the same name "Naruto"
    await db["characters"].insert_one({"_id": "char_n1", "name": "Naruto Uzumaki", "is_deleted": False})
    await db["anime"].insert_one({"_id": "anime_n1", "title": {"english": "Naruto"}, "is_deleted": False})
    
    results = await search_relationship_entities("naruto")
    
    ids = [r["id"] for r in results]
    assert "char_n1" in ids
    assert "anime_n1" in ids
    
    char_res = next(r for r in results if r["id"] == "char_n1")
    anime_res = next(r for r in results if r["id"] == "anime_n1")
    
    assert char_res["entity_type"] == "character"
    assert anime_res["entity_type"] == "anime"
    
    # Clean up
    await db["characters"].delete_many({"_id": "char_n1"})
    await db["anime"].delete_many({"_id": "anime_n1"})
