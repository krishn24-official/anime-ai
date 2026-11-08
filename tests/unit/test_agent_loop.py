from app.domain.llm.entities import ModelReply, ToolCall
from app.services import agent_service


class LoopingModel:
    """Keeps asking for the same tool until it is offered no tools."""

    name = "fake"

    def __init__(self):
        self.calls_without_tools = 0

    async def complete(self, system, messages, tools=None):
        if tools is None:
            self.calls_without_tools += 1
            return ModelReply(text="Luffy has a rubber body (Gomu‑Gomu).", tool_calls=(), provider="fake")
        return ModelReply(text="", tool_calls=(ToolCall("abc123def", "query_lore", {"query": "Luffy powers"}),), provider="fake")


async def test_a_looping_model_still_answers_and_repeats_are_not_rerun(monkeypatch):
    model, executed = LoopingModel(), []

    async def fake_execute(name, args):
        executed.append(name)
        return "Luffy ate the Gomu Gomu no Mi."

    monkeypatch.setattr(agent_service.container, "chat_model", lambda: model)
    monkeypatch.setattr(agent_service, "execute_tool", fake_execute)

    result = await agent_service.run_agent("Tell me about Luffy's powers")

    assert result["answer"] == "Luffy has a rubber body (Gomu-Gomu)."  # odd spaces/hyphens normalised
    assert model.calls_without_tools == 1  # forced to answer on the last step
    assert executed == ["query_lore"]  # the identical repeated call was not run again
    assert result["iterations"] == agent_service.MAX_ITERATIONS
