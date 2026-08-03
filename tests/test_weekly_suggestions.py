import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.repositories.content_repository import get_weekly_suggestions

@pytest.mark.asyncio
async def test_get_weekly_suggestions_deterministic():
    with patch('app.repositories.content_repository.get_db') as mock_get_db, \
         patch('app.repositories.rating_repository.get_top_rated', new_callable=AsyncMock) as mock_get_top_rated, \
         patch('app.repositories.content_repository.datetime') as mock_datetime:
         
        # Mock datetime to control the seed
        mock_now = MagicMock()
        mock_now.isocalendar.return_value = (2023, 10, 1) # 2023-W10
        mock_datetime.now.return_value = mock_now
        
        # Keep timezone intact from original datetime module
        from datetime import timezone
        mock_datetime.timezone = timezone
        
        # Mock DB
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        # Mock fallback cursor
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.to_list = AsyncMock(return_value=[
            {"_id": f"fallback_{i}"} for i in range(1, 11)
        ])
        
        # Mock find for fallback and final doc fetch
        def mock_find(query, projection=None):
            if "is_deleted" in query:
                return mock_cursor
            
            # This is the final doc fetch
            in_ids = query.get("_id", {}).get("$in", [])
            final_cursor = MagicMock()
            final_cursor.to_list = AsyncMock(return_value=[
                {"_id": f"fallback_{i}", "title": f"Fallback {i}", "images": {"poster": "url"}} 
                for i in range(1, 11) if f"fallback_{i}" in in_ids
            ])
            return final_cursor
            
        mock_collection = MagicMock()
        mock_collection.find = mock_find
        mock_db.__getitem__.return_value = mock_collection
        
        # Mock top_rated to return nothing (force fallback)
        mock_get_top_rated.return_value = []
        
        # Call multiple times in the same week, should return same items
        res1 = await get_weekly_suggestions(picks_per_type=2)
        res2 = await get_weekly_suggestions(picks_per_type=2)
        
        assert len(res1) == 8 # 2 per type * 4 types
        assert res1 == res2
        assert all(r["reason"] == "Recently added" for r in res1)
        
        # Change week, should potentially change picks
        mock_now.isocalendar.return_value = (2023, 11, 1)
        res3 = await get_weekly_suggestions(picks_per_type=2)
        
        # Let's ensure the rating pool logic works too.
        mock_get_top_rated.return_value = [
            {"_id": {"content_id": f"rated_{i}"}, "count": 5} for i in range(1, 6)
        ]
        
        def mock_find_rated(query, projection=None):
            in_ids = query.get("_id", {}).get("$in", [])
            final_cursor = MagicMock()
            final_cursor.to_list = AsyncMock(return_value=[
                {"_id": f"rated_{i}", "title": f"Rated {i}"} 
                for i in range(1, 6) if f"rated_{i}" in in_ids
            ])
            return final_cursor
            
        mock_collection.find = mock_find_rated
        
        res4 = await get_weekly_suggestions(picks_per_type=2)
        assert len(res4) == 8
        assert all(r["reason"] == "Highly rated" for r in res4)
