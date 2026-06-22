import os
import asyncio
import pytest

# Ensure we use an isolated test database to protect the working database
os.environ["MONGO_DB_NAME"] = "anime_ai_test"

from app.main import app
from app.db.mongo import connect_db, close_db, get_db
from app.db.indexes import create_indexes
from httpx import AsyncClient, ASGITransport


@pytest.fixture(scope="function", autouse=True)
async def db_setup():
    import app.db.mongo as mongo_module
    # Connect to the test database and ensure indexes are created
    await connect_db()
    await create_indexes()
    
    # Clean up auth collections before each test run for test isolation
    db = get_db()
    collections = ["users", "refresh_tokens"]
    for col in collections:
        await db[col].delete_many({})
        
    yield
    # Drop the test database to clean up after test execution completes
    db = get_db()
    await db.client.drop_database("anime_ai_test")
    await close_db()
    mongo_module.client = None

@pytest.fixture(scope="function")
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
