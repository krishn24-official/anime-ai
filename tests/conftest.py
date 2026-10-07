import os
import asyncio
import pytest

# Ensure we use an isolated test database and test JWT secret
os.environ["MONGO_DB_NAME"] = "anime_ai_test"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-32-chars-long-for-testing"

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
    
    db = get_db()
    if db.name != "anime_ai_test" and "test" not in db.name:
        raise RuntimeError(
            f"SAFETY GUARD: Refusing to run tests against non-test database '{db.name}'!"
        )
    
    # Clean up auth collections before each test run for test isolation
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
