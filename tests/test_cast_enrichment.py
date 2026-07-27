import pytest
from unittest.mock import patch
from app.services.cast_enrichment_service import enrich_cast

@pytest.mark.asyncio
async def test_enrich_cast():
    # Mock cast data from DB
    cast_data = [
        {"actor_id": "actor_1", "character_name": "Hero", "order": 1},
        {"actor_id": "actor_2", "character_name": "Villain", "order": 0},
        {"name": "Legacy Actor", "role": "Sidekick"}, # Legacy format, these are currently ignored by the logic, actually let's see, enrich_cast expects actor_id, if not, it continues.
        {"actor_id": "actor_3", "character_name": "Extra", "order": 2} # Missing in mock DB
    ]
    
    # Mock actors in DB
    mock_actors_db = {
        "actor_1": {"_id": "actor_1", "name": "Real Actor 1", "images": {"profile": "img1.jpg"}},
        "actor_2": {"_id": "actor_2", "name": "Real Actor 2", "images": {"profile": "img2.jpg"}},
        # actor_3 is missing
    }
    
    async def mock_get_actor(actor_id: str):
        return mock_actors_db.get(actor_id)

    with patch('app.repositories.actors_repository.get_actor_by_id', side_effect=mock_get_actor):
        enriched = await enrich_cast(cast_data)
        
    # We expect 2 items (legacy doesn't have actor_id so skipped, actor_3 not found so skipped)
    assert len(enriched) == 2
    
    # Check ordering: order 0 (Villain) then order 1 (Hero)
    
    # Villain (order 0)
    assert enriched[0]["id"] == "actor_2"
    assert enriched[0]["name"] == "Real Actor 2"
    assert enriched[0]["role"] == "Villain"
    assert enriched[0]["image"] == "img2.jpg"
    
    # Hero (order 1)
    assert enriched[1]["id"] == "actor_1"
    assert enriched[1]["name"] == "Real Actor 1"
    assert enriched[1]["role"] == "Hero"
    assert enriched[1]["image"] == "img1.jpg"
