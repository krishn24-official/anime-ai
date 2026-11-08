from datetime import datetime, timedelta, timezone

import pytest

from app.application.llm.service import COOLDOWN, AllModelsUnavailable, FallbackChatModel
from app.domain.llm.entities import ChatMessage, ModelReply, ModelUnavailable

HI = [ChatMessage(role="user", content="hi")]


class FakeModel:
    def __init__(self, name, fail=False):
        self.name, self.fail, self.calls = name, fail, 0

    async def complete(self, system, messages, tools=None):
        self.calls += 1
        if self.fail:
            raise ModelUnavailable("429 quota")
        return ModelReply(text=f"from {self.name}", tool_calls=(), provider=self.name)


async def test_falls_back_in_order_and_cools_down_the_failed_provider():
    now = {"t": datetime(2026, 11, 8, tzinfo=timezone.utc)}
    gemini, groq, mistral = FakeModel("gemini", fail=True), FakeModel("groq"), FakeModel("mistral")
    model = FallbackChatModel([gemini, groq, mistral], clock=lambda: now["t"])

    assert (await model.complete("sys", HI)).provider == "groq"
    await model.complete("sys", HI)
    assert gemini.calls == 1  # skipped while cooling down
    assert mistral.calls == 0  # never needed

    now["t"] += COOLDOWN + timedelta(seconds=1)
    gemini.fail = False
    assert (await model.complete("sys", HI)).provider == "gemini"  # retried after the cooldown


async def test_raises_when_every_provider_fails():
    model = FallbackChatModel([FakeModel("gemini", fail=True), FakeModel("groq", fail=True)])
    with pytest.raises(AllModelsUnavailable):
        await model.complete("sys", HI)


async def test_a_per_minute_limit_only_cools_down_for_as_long_as_the_provider_says():
    now = {"t": datetime(2026, 11, 8, tzinfo=timezone.utc)}

    class RateLimited(FakeModel):
        async def complete(self, system, messages, tools=None):
            self.calls += 1
            if self.fail:
                raise ModelUnavailable("429 tokens per minute", retry_after=20)
            return ModelReply(text="ok", tool_calls=(), provider=self.name)

    groq, mistral = RateLimited("groq", fail=True), FakeModel("mistral")
    model = FallbackChatModel([groq, mistral], clock=lambda: now["t"])
    assert (await model.complete("sys", HI)).provider == "mistral"
    now["t"] += timedelta(seconds=21)  # not 15 minutes
    groq.fail = False
    assert (await model.complete("sys", HI)).provider == "groq"
