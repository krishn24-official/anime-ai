"""ChatModel for Google Gemini (google-genai SDK)."""

import uuid

from google import genai
from google.genai import errors, types

from app.domain.llm.entities import ChatMessage, ModelReply, ModelUnavailable, ToolCall, ToolSpec


def _contents(messages: list[ChatMessage]) -> list[types.Content]:
    contents = []
    for m in messages:
        if m.role == "tool":
            contents.append(types.Content(role="user", parts=[
                types.Part.from_function_response(name=m.name or "tool", response={"result": m.content})
            ]))
        elif m.role == "assistant":
            parts = [types.Part.from_text(text=m.content)] if m.content else []
            parts += [types.Part(function_call=types.FunctionCall(name=c.name, args=c.args)) for c in m.tool_calls]
            contents.append(types.Content(role="model", parts=parts))
        else:
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=m.content)]))
    return contents


class GeminiChatModel:
    def __init__(self, api_key: str | None, model: str):
        self._client = genai.Client(api_key=api_key) if api_key else None
        self._model = model
        self.name = f"gemini:{model}"

    async def complete(self, system: str, messages: list[ChatMessage], tools: list[ToolSpec] | None = None) -> ModelReply:
        if not self._client:
            raise ModelUnavailable("GEMINI_API_KEY is not set")
        config = types.GenerateContentConfig(system_instruction=system)
        if tools:
            config.tools = [types.Tool(function_declarations=[
                types.FunctionDeclaration(name=t.name, description=t.description, parameters=t.parameters) for t in tools
            ])]
            config.automatic_function_calling = types.AutomaticFunctionCallingConfig(disable=True)
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model, contents=_contents(messages), config=config
            )
        except errors.APIError as e:  # 429 quota, 5xx outage, 4xx bad key...
            raise ModelUnavailable(f"{e.code}: {e.message}") from e

        candidate = response.candidates[0] if response.candidates else None
        parts = (candidate.content.parts if candidate and candidate.content else None) or []
        calls = tuple(
            # Gemini has no call ids; Mistral needs 9 alphanumerics if the turn falls back there.
            ToolCall(id=uuid.uuid4().hex[:9], name=p.function_call.name, args=dict(p.function_call.args or {}))
            for p in parts if p.function_call
        )
        text = "".join(p.text for p in parts if p.text).strip()
        return ModelReply(text=text, tool_calls=calls, provider=self.name)
