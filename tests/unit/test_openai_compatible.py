import json

from app.domain.llm.entities import ChatMessage, ToolCall
from app.infrastructure.llm.openai_compatible_model import OpenAICompatibleChatModel, _args, _messages


def test_tool_conversation_maps_to_the_openai_format():
    msgs = _messages("be nice", [
        ChatMessage(role="user", content="who is Gojo?"),
        ChatMessage(role="assistant", tool_calls=(ToolCall("abc123def", "get_character_info", {"name": "Gojo"}),)),
        ChatMessage(role="tool", content="Gojo is a sorcerer.", tool_call_id="abc123def", name="get_character_info"),
    ])
    assert msgs[0] == {"role": "system", "content": "be nice"}
    call = msgs[2]["tool_calls"][0]
    assert call["id"] == "abc123def" and json.loads(call["function"]["arguments"]) == {"name": "Gojo"}
    assert msgs[3] == {"role": "tool", "tool_call_id": "abc123def", "name": "get_character_info", "content": "Gojo is a sorcerer."}


def test_arguments_tolerate_dicts_and_bad_json():
    assert _args('{"a": 1}') == {"a": 1}
    assert _args({"a": 1}) == {"a": 1}
    assert _args("not json") == {}


async def test_missing_key_means_unavailable_not_a_crash():
    import pytest

    from app.domain.llm.entities import ModelUnavailable

    model = OpenAICompatibleChatModel("groq", "https://example.invalid", None, "llama")
    with pytest.raises(ModelUnavailable):
        await model.complete("sys", [ChatMessage(role="user", content="hi")])
