"""ChatModel for OpenAI-compatible chat APIs: Groq and Mistral (plain HTTP, no SDK)."""

import asyncio
import json

import httpx

from app.domain.llm.entities import ChatMessage, ModelReply, ModelUnavailable, ToolCall, ToolSpec

GROQ_URL = "https://api.groq.com/openai/v1"
MISTRAL_URL = "https://api.mistral.ai/v1"
MAX_WAIT_SECONDS = 15  # wait out a per-minute limit up to this long before falling back


def _retry_after(r: httpx.Response) -> float | None:
    try:
        return float(r.headers["retry-after"])
    except (KeyError, ValueError):
        return None


def _messages(system: str, messages: list[ChatMessage]) -> list[dict]:
    out = [{"role": "system", "content": system}]
    for m in messages:
        if m.role == "tool":
            out.append({"role": "tool", "tool_call_id": m.tool_call_id, "name": m.name, "content": m.content})
        elif m.role == "assistant" and m.tool_calls:
            out.append({
                "role": "assistant",
                "content": m.content or "",
                "tool_calls": [
                    {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": json.dumps(c.args)}}
                    for c in m.tool_calls
                ],
            })
        else:
            out.append({"role": m.role, "content": m.content})
    return out


def _args(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}


class OpenAICompatibleChatModel:
    def __init__(self, provider: str, base_url: str, api_key: str | None, model: str, timeout: float = 30):
        self._url = f"{base_url}/chat/completions"
        self._key = api_key
        self._model = model
        self._timeout = timeout
        self.name = f"{provider}:{model}"

    async def complete(self, system: str, messages: list[ChatMessage], tools: list[ToolSpec] | None = None) -> ModelReply:
        if not self._key:
            raise ModelUnavailable(f"{self.name}: API key is not set")
        body: dict = {"model": self._model, "messages": _messages(system, messages)}
        if tools:
            body["tools"] = [
                {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
                for t in tools
            ]
            body["tool_choice"] = "auto"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as http:
                for attempt in range(2):
                    r = await http.post(self._url, json=body, headers={"Authorization": f"Bearer {self._key}"})
                    retry_after = _retry_after(r)
                    if attempt == 0 and r.status_code == 429 and retry_after is not None and retry_after <= MAX_WAIT_SECONDS:
                        await asyncio.sleep(retry_after)  # per-minute token/request limit: wait it out
                        continue
                    # Groq sometimes rejects a model's malformed tool call; a second try usually works.
                    if not (r.status_code == 400 and "tool_use_failed" in r.text):
                        break
        except httpx.HTTPError as e:
            raise ModelUnavailable(f"{self.name}: {e}") from e
        if r.status_code != 200:  # 429 rate limit / quota, 401 bad key, 5xx outage, 400 failed tool call
            raise ModelUnavailable(f"{self.name}: HTTP {r.status_code} {r.text[:200]}", retry_after=_retry_after(r))

        message = (r.json().get("choices") or [{}])[0].get("message") or {}
        calls = tuple(
            ToolCall(id=c.get("id") or f"call{i:05d}", name=c["function"]["name"], args=_args(c["function"].get("arguments")))
            for i, c in enumerate(message.get("tool_calls") or [])
        )
        return ModelReply(text=(message.get("content") or "").strip(), tool_calls=calls, provider=self.name)
