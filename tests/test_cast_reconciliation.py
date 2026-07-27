import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.cast_reconciliation_service import resolve_or_create_actor, reconcile_cast

@pytest.mark.asyncio
async def test_resolve_or_create_actor_existing():
    # Setup mocks
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_db.__getitem__.return_value = mock_collection
    
    mock_collection.find_one = AsyncMock(return_value={"_id": "actor_john_doe"})
    
    with patch("app.services.cast_reconciliation_service.get_db", return_value=mock_db):
        actor_id = await resolve_or_create_actor(12345, "John Doe", "img.jpg")
        
        assert actor_id == "actor_john_doe"
        mock_collection.find_one.assert_called_once_with({"tmdb_id": 12345, "is_deleted": False})

@pytest.mark.asyncio
async def test_resolve_or_create_actor_new():
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_db.__getitem__.return_value = mock_collection
    
    mock_collection.find_one = AsyncMock(side_effect=[None, None])
    
    async def mock_get_person(tmdb_id):
        return {
            "name": "Jane Doe",
            "birthday": "1990-01-01",
            "biography": "A cool person",
            "profile_path": "/jane.jpg"
        }
        
    async def mock_create_actor(doc):
        return doc["_id"]
        
    with patch("app.services.cast_reconciliation_service.get_db", return_value=mock_db), \
         patch("app.services.cast_reconciliation_service.get_person_details", new_callable=AsyncMock) as mock_get, \
         patch("app.repositories.actors_repository.create_actor", new_callable=AsyncMock) as mock_create:
        
        mock_get.side_effect = mock_get_person
        mock_create.side_effect = mock_create_actor
        
        print("Calling resolve_or_create_actor for Jane")
        actor_id = await resolve_or_create_actor(54321, "Jane", None)
        print(f"Finished resolve_or_create_actor for Jane: {actor_id}")
        
        assert actor_id == "actor_jane-doe"
        mock_create.assert_called_once()
        doc = mock_create.call_args[0][0]
        assert doc["tmdb_id"] == 54321
        assert doc["name"] == "Jane Doe"
        assert doc["birthdate"] == "1990-01-01"
        assert doc["images"]["profile"] == "https://image.tmdb.org/t/p/original/jane.jpg"

@pytest.mark.asyncio
async def test_resolve_or_create_actor_fallback():
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_db.__getitem__.return_value = mock_collection
    
    mock_collection.find_one = AsyncMock(side_effect=[None, None])
    
    # Fetch returns None (TMDB failure)
    async def mock_get_person(tmdb_id):
        return None
        
    async def mock_create_actor(doc):
        return doc["_id"]
        
    with patch("app.services.cast_reconciliation_service.get_db", return_value=mock_db), \
         patch("app.services.cast_reconciliation_service.get_person_details", side_effect=mock_get_person), \
         patch("app.repositories.actors_repository.create_actor", side_effect=mock_create_actor) as mock_create:
        
        # Uses provided name and image from fallback
        actor_id = await resolve_or_create_actor(9999, "Fallback Actor", "fallback.jpg")
        
        assert actor_id == "actor_fallback-actor"
        mock_create.assert_called_once()
        doc = mock_create.call_args[0][0]
        assert doc["name"] == "Fallback Actor"
        assert doc["images"]["profile"] == "fallback.jpg"
        assert doc["birthdate"] is None

@pytest.mark.asyncio
async def test_reconcile_cast():
    raw_cast = [
        {"tmdb_person_id": 1, "name": "Actor A", "character": "Char A", "profile_image": "img1.jpg"},
        {"tmdb_person_id": 2, "name": "Actor B", "character": "Char B", "profile_image": "img2.jpg"},
        # No tmdb_id fallback handling check
        {"tmdb_person_id": None, "name": "No TMDB", "character": "Extra", "profile_image": None},
    ]
    
    async def mock_resolve(tmdb_id, name, img):
        if tmdb_id == 1:
            return "actor_1"
        elif tmdb_id == 2:
            return "actor_2"
        return None
        
    with patch("app.services.cast_reconciliation_service.resolve_or_create_actor", new_callable=AsyncMock) as mock_resolve_actor:
        mock_resolve_actor.side_effect = mock_resolve
        reconciled = await reconcile_cast(raw_cast)
        
        # Should drop the 3rd one since it resolved to None
        assert len(reconciled) == 2
        
        assert reconciled[0]["actor_id"] == "actor_1"
        assert reconciled[0]["character_name"] == "Char A"
        assert reconciled[0]["order"] == 0
        
        assert reconciled[1]["actor_id"] == "actor_2"
        assert reconciled[1]["character_name"] == "Char B"
        assert reconciled[1]["order"] == 1
