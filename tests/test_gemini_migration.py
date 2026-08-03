import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import base64
from google.genai import types

from app.services.game_property_extractor import extract_game_properties
from app.services.gemini_service import (
    ask_gemini_with_context,
    identify_image,
    categorize_and_summarize_news
)
from app.services.agent_service import run_agent

@pytest.mark.asyncio
@patch("app.services.game_property_extractor.genai.Client")
async def test_game_property_extractor(mock_client_cls):
    mock_client = MagicMock()
    mock_aio_client = MagicMock()
    mock_client.aio = mock_aio_client
    mock_client_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.text = '{"isMale": true, "hasBlackHair": true, "isNinja": false}'
    mock_aio_client.models.generate_content = AsyncMock(return_value=mock_response)

    properties = await extract_game_properties("Kirito", "Black swordsman", "Male", ["Sword Art Online"])

    assert "isMale" in properties
    assert "hasBlackHair" in properties
    assert "isNinja" not in properties
    mock_aio_client.models.generate_content.assert_called_once()
    kwargs = mock_aio_client.models.generate_content.call_args.kwargs
    assert kwargs["model"] == "gemini-2.5-flash-lite"


@pytest.mark.asyncio
@patch("app.services.gemini_service._client")
async def test_gemini_service_news(mock_client):
    mock_aio_client = MagicMock()
    mock_client.aio = mock_aio_client
    mock_response = MagicMock()
    mock_response.text = '{"category": "Anime", "summary": "A test summary."}'
    mock_aio_client.models.generate_content = AsyncMock(return_value=mock_response)

    result = await categorize_and_summarize_news("Test title", "Test description")
    
    assert result == {"category": "Anime", "summary": "A test summary."}
    mock_aio_client.models.generate_content.assert_called_once()
    kwargs = mock_aio_client.models.generate_content.call_args.kwargs
    assert kwargs["model"] == "gemini-2.5-flash-lite"


@pytest.mark.asyncio
@patch("app.services.gemini_service._client")
async def test_gemini_service_ask_context(mock_client):
    mock_aio_client = MagicMock()
    mock_client.aio = mock_aio_client
    mock_response = MagicMock()
    mock_response.text = "Here is the answer based on context."
    mock_aio_client.models.generate_content = AsyncMock(return_value=mock_response)

    result = await ask_gemini_with_context("Who is this?", {"name": "Luffy"})
    
    assert result == "Here is the answer based on context."


@pytest.mark.asyncio
@patch("app.services.gemini_service._client")
@patch("base64.b64decode")
@patch("app.services.gemini_service.types.Part.from_bytes")
async def test_gemini_service_identify_image(mock_from_bytes, mock_b64decode, mock_client):
    mock_aio_client = MagicMock()
    mock_client.aio = mock_aio_client
    mock_response = MagicMock()
    mock_response.text = "This is Zoro."
    mock_aio_client.models.generate_content = AsyncMock(return_value=mock_response)

    mock_b64decode.return_value = b"raw_image_data"
    mock_part = MagicMock()
    mock_from_bytes.return_value = mock_part

    test_base64 = "some_base64_string"
    result = await identify_image("Who is this?", test_base64, "image/png")
    
    # Assert base64.b64decode is actually called on the input
    mock_b64decode.assert_called_once_with(test_base64)
    # Assert from_bytes is called with the decoded raw bytes, NOT the base64 string
    mock_from_bytes.assert_called_once_with(data=b"raw_image_data", mime_type="image/png")
    
    assert result == "This is Zoro."


@pytest.mark.asyncio
@patch("app.services.agent_service.genai.Client")
@patch("app.services.agent_service.execute_tool")
async def test_agent_service_intent_path(mock_execute_tool, mock_client_cls):
    mock_client = MagicMock()
    mock_aio_client = MagicMock()
    mock_client.aio = mock_aio_client
    mock_client_cls.return_value = mock_client

    # Intent matched: latest news
    mock_execute_tool.return_value = "News data here"
    
    mock_response = MagicMock()
    mock_response.text = "Here is the synthesized news."
    mock_aio_client.models.generate_content = AsyncMock(return_value=mock_response)

    result = await run_agent("latest news")
    
    assert result["answer"] == "Here is the synthesized news."
    assert result["tools_used"] == ["get_latest_news"]
    assert result["iterations"] == 1


@pytest.mark.asyncio
@patch("app.services.agent_service.genai.Client")
@patch("app.services.agent_service.execute_tool")
async def test_agent_service_tool_loop(mock_execute_tool, mock_client_cls):
    mock_client = MagicMock()
    mock_aio_client = MagicMock()
    mock_client.aio = mock_aio_client
    mock_client_cls.return_value = mock_client

    # We need to simulate two calls to generate_content:
    # 1st call: returns a function_call part
    # 2nd call: returns final text
    
    mock_response_1 = MagicMock()
    mock_candidate_1 = MagicMock()
    mock_part_1 = types.Part(
        function_call=types.FunctionCall(
            name="search_content",
            args={"query": "test query"}
        )
    )
    
    mock_candidate_1.content.parts = [mock_part_1]
    mock_response_1.candidates = [mock_candidate_1]
    
    # Second response mock (final text)
    mock_response_2 = MagicMock()
    mock_candidate_2 = MagicMock()
    mock_part_2 = types.Part.from_text(text="Final answer from agent.")
    mock_candidate_2.content.parts = [mock_part_2]
    mock_response_2.candidates = [mock_candidate_2]

    # Assign side effect
    mock_aio_client.models.generate_content = AsyncMock(side_effect=[mock_response_1, mock_response_2])
    
    mock_execute_tool.return_value = "Search result from DB"

    result = await run_agent("complex query that requires tools")
    
    assert result["answer"] == "Final answer from agent."
    assert result["tools_used"] == ["search_content"]
    assert result["iterations"] == 2
    
    mock_execute_tool.assert_called_once_with("search_content", {"query": "test query"})
