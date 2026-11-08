"""Chat with automatic fallback across free-tier providers (Gemini -> Groq -> Mistral)."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable

from app.domain.llm.entities import ChatMessage, ModelReply, ModelUnavailable, ToolSpec
from app.domain.llm.ports import ChatModel

logger = logging.getLogger(__name__)

# A provider that ran out of quota is skipped for a while instead of being retried
# (and failing) on every question.
COOLDOWN = timedelta(minutes=15)


class AllModelsUnavailable(Exception):
    """Every configured provider is out of quota or failing."""


class FallbackChatModel:
    """A ChatModel that tries each provider in order, skipping ones cooling down."""

    def __init__(self, models: list[ChatModel], clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        self._models = models
        self._clock = clock
        self._cooling: dict[str, datetime] = {}  # provider name -> retry after
        self.name = "fallback(" + ", ".join(m.name for m in models) + ")"

    async def complete(
        self, system: str, messages: list[ChatMessage], tools: list[ToolSpec] | None = None
    ) -> ModelReply:
        now = self._clock()
        available = [m for m in self._models if self._cooling.get(m.name, now) <= now]
        # If everything is cooling down, try them all anyway: quotas may have reset.
        for model in available or self._models:
            try:
                reply = await model.complete(system, messages, tools)
                self._cooling.pop(model.name, None)
                return reply
            except ModelUnavailable as e:
                logger.warning("model %s unavailable, falling back: %s", model.name, e)
                # Per-minute limits clear in seconds; only an unexplained failure parks it longer.
                wait = timedelta(seconds=e.retry_after) if e.retry_after else COOLDOWN
                self._cooling[model.name] = now + wait
        raise AllModelsUnavailable("no model available")
