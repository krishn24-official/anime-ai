import pytest
from unittest.mock import patch, AsyncMock
from app.services.character_profile_formatter import format_character_profile
from app.services.chat_service import process_chat_message

def test_format_character_profile_skips_empty_family_member():
    character = {"name": "Naruto Uzumaki"}
    details = {
        "family": [
            {"target": {"name": "Minato Namikaze"}, "relation": "father"},
            {"target": {"name": ""}, "relation": "mother"},
            {"target": {"name": "  "}, "relation": "brother"},
            {"target": {"name": "Boruto Uzumaki"}, "relation": "son"}
        ]
    }
    
    result = format_character_profile(character, details)
    
    assert "Minato Namikaze (father)" in result
    assert "Boruto Uzumaki (son)" in result
    assert "()" not in result
    assert "(mother)" not in result
    assert "(brother)" not in result

def test_format_character_profile_omits_empty_family_section():
    character = {"name": "Naruto Uzumaki"}
    details = {
        "family": [
            {"target": {"name": ""}, "relation": "mother"},
            {"target": {"name": "  "}, "relation": "brother"}
        ]
    }
    
    result = format_character_profile(character, details)
    
    assert "Family" not in result

def test_format_character_profile_omits_missing_stats():
    character = {"name": "Naruto Uzumaki", "birthday": "October 10"}
    details = {}
    
    result = format_character_profile(character, details)
    
    assert "Born October 10" in result
    assert " • " not in result # No separators since there's only one stat

    character2 = {"name": "Naruto", "gender": "Male", "height": "166 cm"}
    result2 = format_character_profile(character2, details)
    assert "Male • 166 cm" in result2
    assert "Born" not in result2

def test_format_character_profile_biography():
    character = {"name": "Naruto", "description": "A ninja."}
    details = {}
    
    result = format_character_profile(character, details)
    assert "**Biography**\nA ninja." in result
    
    character2 = {"name": "Naruto"}
    result2 = format_character_profile(character2, details)
    assert "Biography" not in result2

@pytest.mark.asyncio
@patch("app.services.chat_service.find_character_candidates")
@patch("app.services.chat_service.build_character_context")
@patch("app.services.chat_service.ask_gemini_with_context")
@patch("app.services.chat_service.detect_intent")
async def test_unknown_intent_uses_formatter_no_gemini(mock_detect_intent, mock_ask_gemini, mock_build_context, mock_find_candidates):
    mock_find_candidates.return_value = [{"_id": "c1", "name": "Sasuke Uchiha"}]
    mock_detect_intent.return_value = "unknown"
    mock_build_context.return_value = {}
    
    result = await process_chat_message("tell me about sasuke")
    
    assert "answer" in result
    assert "Sasuke Uchiha" in result["answer"]
    assert mock_ask_gemini.call_count == 0

from app.services.content_profile_formatter import format_content_profile

def test_format_content_profile_anime():
    anime = {
        "title": {"english": "Naruto"},
        "year": 2002,
        "status": "Finished",
        "genres": ["Action", "Adventure"],
        "total_episodes": 220,
        "rating": {"anilist": None},
        "description": "Ninja story."
    }
    result = format_content_profile(anime, "anime")
    assert "**Naruto** (2002)" in result
    assert "Finished • Action, Adventure • 220 episodes" in result
    assert "Rated" not in result
    assert "Ninja story." in result

def test_format_content_profile_movie():
    movie = {
        "title": "Your Name",
        "year": 2016,
        "status": "Released",
        "genres": [],
        "runtime_minutes": 106,
        "rating": {"tmdb": 8.5},
        "plot": "Body swap."
    }
    result = format_content_profile(movie, "movie")
    assert "**Your Name** (2016)" in result
    assert "Released • 106 min • Rated 8.5" in result
    assert "Body swap." in result

def test_format_content_profile_tv_series():
    tv = {
        "title": "Breaking Bad",
        "year": 2008,
        "status": "Ended",
        "genres": ["Drama"],
        "total_seasons": 5,
        "total_episodes": 62,
        "rating": {"tmdb": 9.3},
        "plot": "Meth."
    }
    result = format_content_profile(tv, "tv_series")
    assert "**Breaking Bad** (2008)" in result
    assert "Ended • Drama • 5 seasons, 62 episodes • Rated 9.3" in result
    assert "Meth." in result

@pytest.mark.asyncio
@patch("app.repositories.search_repository.search_anime")
async def test_chat_anime_intent(mock_search_anime):
    mock_search_anime.return_value = [{"title": {"english": "Bleach"}, "description": "Soul reapers."}]
    result = await process_chat_message("tell me about the anime Bleach")
    assert "answer" in result
    assert "**Bleach**" in result["answer"]
    assert "Soul reapers." in result["answer"]

@pytest.mark.asyncio
@patch("app.repositories.search_repository.search_movies")
async def test_chat_movie_intent(mock_search_movies):
    mock_search_movies.return_value = [{"title": "Inception", "plot": "Dreams."}]
    result = await process_chat_message("tell me about the movie Inception")
    assert "answer" in result
    assert "**Inception**" in result["answer"]
    assert "Dreams." in result["answer"]

@pytest.mark.asyncio
@patch("app.repositories.search_repository.search_tv_series")
async def test_chat_tv_series_intent(mock_search_tv):
    mock_search_tv.return_value = [{"title": "The Wire", "plot": "Baltimore."}]
    result = await process_chat_message("tell me about the tv show The Wire")
    assert "answer" in result
    assert "**The Wire**" in result["answer"]
    assert "Baltimore." in result["answer"]
