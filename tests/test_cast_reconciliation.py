import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.cast_reconciliation_service import resolve_or_create_actor, reconcile_cast, reconcile_directors, reconcile_creators, reconcile_writers, reconcile_writers

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
    
    mock_collection.find_one = AsyncMock(side_effect=[None, None, None])
    
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
        
        assert actor_id == "actor_jane"
        mock_create.assert_called_once()
        doc = mock_create.call_args[0][0]
        assert doc["tmdb_id"] == 54321
        assert doc["name"] == "Jane"
        assert doc["birthdate"] == "1990-01-01"
        assert doc["images"]["profile"] == "https://image.tmdb.org/t/p/original/jane.jpg"

@pytest.mark.asyncio
async def test_resolve_or_create_actor_fallback():
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_db.__getitem__.return_value = mock_collection
    
    mock_collection.find_one = AsyncMock(side_effect=[None, None, None])
    
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
        
        assert actor_id == "actor_fallback_actor"
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

@pytest.mark.asyncio
async def test_resolve_or_create_actor_legacy_existing():
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_db.__getitem__.return_value = mock_collection
    
    mock_collection.find_one = AsyncMock(return_value={"_id": "actor_legacy_match"})
    
    with patch("app.services.cast_reconciliation_service.get_db", return_value=mock_db):
        actor_id = await resolve_or_create_actor(None, "Legacy Director", None)
        
        assert actor_id == "actor_legacy_match"
        import re
        mock_collection.find_one.assert_called_once_with({"name": re.compile(f"^{re.escape('Legacy Director')}\\s*$", re.IGNORECASE), "is_deleted": False})

@pytest.mark.asyncio
async def test_resolve_or_create_actor_legacy_new():
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_db.__getitem__.return_value = mock_collection
    
    # First find_one is for the exact name match (returns None)
    # Second find_one is the while loop uniqueness check (returns None)
    mock_collection.find_one = AsyncMock(side_effect=[None, None])
    
    async def mock_create_actor(doc):
        return doc["_id"]
        
    with patch("app.services.cast_reconciliation_service.get_db", return_value=mock_db), \
         patch("app.repositories.actors_repository.create_actor", side_effect=mock_create_actor) as mock_create:
        
        actor_id = await resolve_or_create_actor(None, "Legacy Director", None)
        
        assert actor_id == "actor_legacy_director"
        mock_create.assert_called_once()
        doc = mock_create.call_args[0][0]
        assert doc["name"] == "Legacy Director"
        assert doc["tmdb_id"] is None
        assert doc["images"]["profile"] is None
        assert doc["source_metadata"]["source"] == "legacy_backfill"

@pytest.mark.asyncio
async def test_reconcile_directors():
    raw_directors = [
        {"tmdb_person_id": 1, "name": "Director A", "profile_image": "img1.jpg"},
        # Legacy plain-string director
        {"tmdb_person_id": None, "name": "Legacy Director", "profile_image": None},
    ]
    
    async def mock_resolve(tmdb_id, name, img):
        if tmdb_id == 1:
            return "actor_1"
        if tmdb_id is None and name == "Legacy Director":
            return "actor_legacy"
        return None
        
    with patch("app.services.cast_reconciliation_service.resolve_or_create_actor", new_callable=AsyncMock) as mock_resolve_actor:
        mock_resolve_actor.side_effect = mock_resolve
        reconciled = await reconcile_directors(raw_directors)
        
        assert len(reconciled) == 2
        
        assert reconciled[0]["actor_id"] == "actor_1"
        assert reconciled[0]["order"] == 0
        assert "character_name" not in reconciled[0]
        
        assert reconciled[1]["actor_id"] == "actor_legacy"
        assert reconciled[1]["order"] == 1

@pytest.mark.asyncio
async def test_reconcile_writers_legacy_string():
    raw_writers = [
        {"tmdb_person_id": None, "name": "Legacy Writer", "profile_image": None},
    ]
    
    async def mock_resolve(tmdb_id, name, img):
        if tmdb_id is None and name == "Legacy Writer":
            return "actor_legacy_writer"
        return None
        
    with patch("app.services.cast_reconciliation_service.resolve_or_create_actor", new_callable=AsyncMock) as mock_resolve_actor:
        mock_resolve_actor.side_effect = mock_resolve
        reconciled = await reconcile_writers(raw_writers)
        
        assert len(reconciled) == 1
        assert reconciled[0]["actor_id"] == "actor_legacy_writer"
        assert reconciled[0]["order"] == 0

@pytest.mark.asyncio
async def test_fetch_actor_filmography_grouping():
    from app.services.actors_service import fetch_actor_filmography
    
    mock_db = MagicMock()
    mock_movies = MagicMock()
    mock_tv = MagicMock()
    
    def get_collection(name):
        if name == "movies": return mock_movies
        if name == "tv_series": return mock_tv
        return MagicMock()
        
    mock_db.__getitem__.side_effect = get_collection
    
    # Mock finding
    mock_movies_cursor = AsyncMock()
    mock_movies.find.return_value = mock_movies_cursor
    
    mock_tv_cursor = AsyncMock()
    mock_tv.find.return_value = mock_tv_cursor
    
    actor = {"_id": "actor_test", "name": "Test Actor"}
    
    # movie_1: actor in cast only
    # movie_2: actor in writer only
    # movie_3: actor in BOTH cast and writer
    mock_movies_cursor.to_list.return_value = [
        {
            "_id": "movie_1", "title": "Movie 1", "year": "2020", "content_type": "movie",
            "cast": [{"actor_id": "actor_test"}],
            "writer": []
        },
        {
            "_id": "movie_2", "title": "Movie 2", "year": "2021", "content_type": "movie",
            "cast": [],
            "writer": [{"actor_id": "actor_test"}]
        },
        {
            "_id": "movie_3", "title": "Movie 3", "year": "2022", "content_type": "movie",
            "cast": [{"actor_id": "actor_test"}],
            "writer": [{"actor_id": "actor_test"}]
        }
    ]
    
    mock_tv_cursor.to_list.return_value = []
    
    with patch("app.db.mongo.get_db", return_value=mock_db):
        result = await fetch_actor_filmography(actor)
        
        # Test 1 & 2: grouping logic
        assert "as_actor" in result
        assert "as_writer" in result
        
        actor_ids = [m["id"] for m in result["as_actor"]]
        writer_ids = [m["id"] for m in result["as_writer"]]
        
        # Test 1: different titles split correctly
        assert "movie_1" in actor_ids
        assert "movie_2" not in actor_ids
        
        assert "movie_2" in writer_ids
        assert "movie_1" not in writer_ids
        
        # Test 2: same title duplicated correctly in both groups
        assert "movie_3" in actor_ids
        assert "movie_3" in writer_ids
        
        # Test 3: empty group omitted
        assert "as_director" not in result
