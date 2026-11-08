from typing import Protocol

from app.domain.llm.entities import ChatMessage, ModelReply, ToolSpec


class ChatModel(Protocol):
    name: str  # e.g. "gemini:gemini-2.5-flash-lite"

    async def complete(
        self, system: str, messages: list[ChatMessage], tools: list[ToolSpec] | None = None
    ) -> ModelReply:
        """One model turn. Raises ModelUnavailable when another provider should be tried."""
        ...
