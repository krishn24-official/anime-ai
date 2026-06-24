import pytest
from httpx import AsyncClient
from app.db.mongo import get_db

@pytest.fixture(autouse=True)
async def seed_organizations_test_data():
    db = get_db()
    # Clean and insert dummy characters
    await db["characters"].delete_many({})
    await db["organizations"].delete_many({})

    await db["characters"].insert_many([
        {
            "_id": "char_naruto_uzumaki",
            "name": "Naruto Uzumaki",
            "images": {
                "profile": "https://example.com/naruto.png",
                "banner": ""
            },
            "affiliations": ["Konoha"],
            "role": "Shinobi",
            "is_deleted": False
        },
        {
            "_id": "char_kakashi_hatake",
            "name": "Kakashi Hatake",
            "images": {
                "profile": "https://example.com/kakashi.png",
                "banner": ""
            },
            "affiliations": ["Konoha"],
            "role": "Shinobi / Sensei",
            "is_deleted": False
        },
        {
            "_id": "char_pain",
            "name": "Pain",
            "images": {
                "profile": "https://example.com/pain.png",
                "banner": ""
            },
            "affiliations": ["Akatsuki"],
            "role": "Leader",
            "is_deleted": False
        }
    ])

    await db["organizations"].insert_many([
        {
            "_id": "org_konohagakure",
            "name": "Konoha",
            "type": "village",
            "status": "active",
            "description": "Hidden Leaf Village",
            "leader_id": "char_naruto_uzumaki",
            "founded_by_id": "char_hashirama_senju",
            "headquarters": None,
            "anime_ids": ["anime_naruto"],
            "manga_id": "manga_naruto",
            "images": {
                "logo": "https://example.com/konoha_logo.png",
                "banner": "https://example.com/konoha_banner.png"
            },
            "tags": ["ninja", "village"],
            "members": [
                { "char_id": "char_naruto_uzumaki", "title": "7th Hokage", "order": 7 }
            ],
            "is_deleted": False
        },
        {
            "_id": "org_akatsuki",
            "name": "Akatsuki",
            "type": "organization",
            "status": "disbanded",
            "description": "Rogue ninja group",
            "leader_id": "char_pain",
            "founded_by_id": "char_yahiko",
            "headquarters": None,
            "anime_ids": ["anime_naruto"],
            "manga_id": "manga_naruto",
            "images": {
                "logo": "https://example.com/akatsuki.png",
                "banner": ""
            },
            "tags": ["rogue"],
            "members": [
                { "char_id": "char_pain", "title": "Leader", "order": 1 }
            ],
            "is_deleted": False
        }
    ])


async def test_get_all_organizations(client: AsyncClient):
    # Test getting all organizations without filter
    res = await client.get("/organizations")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert data["total"] == 2
    assert len(data["items"]) == 2

    # Test filtering by type
    res = await client.get("/organizations?type=village")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == "org_konohagakure"


async def test_get_single_organization(client: AsyncClient):
    res = await client.get("/organizations/org_konohagakure")
    assert res.status_code == 200
    org = res.json()
    assert org["id"] == "org_konohagakure"
    assert org["name"] == "Konoha"
    assert org["type"] == "village"
    assert org["status"] == "active"
    assert org["manga_id"] == "manga_naruto"

    # Verify leader enriched
    assert org["leader"] is not None
    assert org["leader"]["id"] == "char_naruto_uzumaki"
    assert org["leader"]["name"] == "Naruto Uzumaki"
    assert org["leader"]["image"] == "https://example.com/naruto.png"

    # Verify members enriched
    assert len(org["members"]) == 1
    assert org["members"][0]["char_id"] == "char_naruto_uzumaki"
    assert org["members"][0]["character"]["name"] == "Naruto Uzumaki"

    # Verify affiliated characters (both Naruto and Kakashi list "Konoha" as affiliation)
    assert len(org["affiliated_characters"]) == 2
    char_names = [c["name"] for c in org["affiliated_characters"]]
    assert "Naruto Uzumaki" in char_names
    assert "Kakashi Hatake" in char_names


async def test_get_single_organization_not_found(client: AsyncClient):
    res = await client.get("/organizations/nonexistent")
    assert res.status_code == 404


async def test_search_organizations(client: AsyncClient):
    res = await client.get("/organizations/search?q=akatsuki")
    assert res.status_code == 200
    results = res.json()
    assert len(results) == 1
    assert results[0]["id"] == "org_akatsuki"
    assert results[0]["name"] == "Akatsuki"


async def test_get_organizations_by_anime(client: AsyncClient):
    res = await client.get("/organizations/anime/anime_naruto")
    assert res.status_code == 200
    results = res.json()
    assert len(results) == 2
    org_ids = [r["id"] for r in results]
    assert "org_konohagakure" in org_ids
    assert "org_akatsuki" in org_ids


async def test_global_search_integration(client: AsyncClient):
    res = await client.get("/search?q=konoha")
    assert res.status_code == 200
    data = res.json()
    assert "organizations" in data
    assert len(data["organizations"]) == 1
    assert data["organizations"][0]["id"] == "org_konohagakure"


async def test_character_detail_affiliation_linking(client: AsyncClient):
    res = await client.get("/characters/char_naruto_uzumaki/details")
    assert res.status_code == 200
    data = res.json()
    assert "organizations" in data
    assert len(data["organizations"]) == 1
    assert data["organizations"][0]["id"] == "org_konohagakure"
    assert data["organizations"][0]["name"] == "Konoha"


async def test_agent_organization_tools():
    from app.services.agent_tools import execute_tool
    import json

    # Test search_content tool includes organizations
    search_res_str = await execute_tool("search_content", {"query": "konoha"})
    search_res = json.loads(search_res_str)
    assert "organizations" in search_res
    assert len(search_res["organizations"]) == 1
    assert search_res["organizations"][0]["name"] == "Konoha"

    # Test get_organization_info tool
    org_info_str = await execute_tool("get_organization_info", {"name": "Akatsuki"})
    org_info = json.loads(org_info_str)
    assert org_info["name"] == "Akatsuki"
    assert org_info["status"] == "disbanded"
    assert org_info["leader"]["name"] == "Pain"
