"""Provider-independent chat vocabulary (Gemini, Groq, Mistral, ... all map to it)."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict  # JSON schema of the arguments


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    args: dict


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "user", "assistant" or "tool"
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = field(default_factory=tuple)  # assistant asking for tools
    tool_call_id: str | None = None  # tool result: which call it answers
    name: str | None = None  # tool result: tool name


@dataclass(frozen=True)
class ModelReply:
    text: str
    tool_calls: tuple[ToolCall, ...]
    provider: str  # which model answered, e.g. "groq:llama-3.3-70b-versatile"


class ModelUnavailable(Exception):
    """Quota exhausted, rate limited, not configured or down: try another provider."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after  # seconds until the provider expects to work again, if it said
