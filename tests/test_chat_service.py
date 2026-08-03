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
    character = {"name": "Naruto Uzumaki", "birth_month": 10, "birth_day": 10}
    details = {}

    result = format_character_profile(character, details)

    assert "Born 10/10" in result
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

from app.services.actor_profile_formatter import format_actor_profile

def test_format_actor_profile_full():
    actor = {
        "name": "Junko Takeuchi",
        "birthdate": "1972-04-05",
        "biography": "Japanese voice actress."
    }
    known_for = [
        {"title": "Naruto", "year": "2002"},
        {"title": "Hunter x Hunter"}
    ]
    result = format_actor_profile(actor, known_for)
    assert "**Junko Takeuchi**" in result
    assert "Born 4/5" in result
    assert "**Biography**\nJapanese voice actress." in result
    assert "**Known For**\nNaruto (2002), Hunter x Hunter" in result

def test_format_actor_profile_missing_sections():
    actor = {"name": "Unknown Actor"}
    result = format_actor_profile(actor, [])
    assert "**Unknown Actor**" in result
    assert "Born" not in result
    assert "Biography" not in result
    assert "Known For" not in result

@pytest.mark.asyncio
@patch("app.repositories.actors_repository.find_actor_candidates")
@patch("app.services.chat_service.find_character_candidates")
@patch("app.repositories.relationship_repository.search_relationship_entities")
@patch("app.services.actors_service.fetch_actor_filmography")
async def test_chat_actor_intent(mock_fetch_actor_filmography, mock_search_rel, mock_find_char, mock_find_actor):
    mock_find_char.return_value = []
    mock_search_rel.return_value = []
    mock_find_actor.return_value = [{"_id": "a1", "name": "Junko Takeuchi"}]
    mock_fetch_actor_filmography.return_value = []
    
    result = await process_chat_message("tell me about Junko Takeuchi")
    assert "answer" in result
    assert "**Junko Takeuchi**" in result["answer"]

@pytest.mark.asyncio
@patch("app.repositories.actors_repository.find_actor_candidates")
@patch("app.services.chat_service.find_character_candidates")
@patch("app.repositories.relationship_repository.search_relationship_entities")
async def test_chat_actor_disambiguation(mock_search_rel, mock_find_char, mock_find_actor):
    mock_find_char.return_value = []
    mock_search_rel.return_value = []
    mock_find_actor.return_value = [
        {"_id": "a1", "name": "Chris Smith"},
        {"_id": "a2", "name": "Chris Smith Jr"}
    ]
    
    result = await process_chat_message("tell me about chris smith")
    assert "disambiguation" in result
    assert any("Actor: Chris Smith" in d for d in result["disambiguation"])
    assert any("Actor: Chris Smith Jr" in d for d in result["disambiguation"])

@pytest.mark.asyncio
@patch("app.repositories.actors_repository.find_actor_candidates")
@patch("app.services.chat_service.find_character_candidates")
@patch("app.repositories.relationship_repository.search_relationship_entities")
@patch("app.services.chat_service.ask_gemini_with_context")
async def test_chat_gemini_fallback(mock_ask_gemini, mock_search_rel, mock_find_char, mock_find_actor):
    mock_find_char.return_value = []
    mock_search_rel.return_value = []
    mock_find_actor.return_value = []
    mock_ask_gemini.return_value = "Gemini answer"
    
    result = await process_chat_message("tell me about some random thing")
    assert result["answer"] == "Gemini answer"
