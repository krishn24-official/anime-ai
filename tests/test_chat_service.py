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
