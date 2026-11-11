"""
Agentic AI service: tool calling over whichever chat model is available.

The loop:
  1. Send the user message + tool definitions to the model (Gemini, else Groq, else Mistral)
  2. The model asks for tool call(s)
  3. We execute those tools against our real DB
  4. Send results back to the model
  5. Repeat until it produces a final text response (no more tool calls)
"""

import re

from app import container
from app.application.llm.service import AllModelsUnavailable
from app.domain.llm.entities import ChatMessage, ToolSpec
from app.domain.guide.question import is_exact_question
from app.services.agent_tool_definitions import AGENT_TOOLS, AGENT_SYSTEM_PROMPT
from app.services.agent_tools import execute_tool

MAX_ITERATIONS = 5  # safety cap on tool-call rounds

# Intent patterns: map regex → (tool_name, arg_builder)
# These fire BEFORE sending to Gemini, routing obvious queries directly.
# "What should I watch after Frieren?", "anime like Naruto", "if I liked Berserk, ..."
SIMILAR_TITLE = re.compile(
    r"\b(?:after|similar to|like|if i (?:liked|loved|enjoyed))\s+(?P<title>[^?!.,]+)", re.I
)
WANTS_SUGGESTION = re.compile(
    r"\b(watch|read|recommend|suggest|similar|anime|manga|movies?|shows?|series)\b", re.I
)


def _similar_title_args(message: str) -> dict | None:
    match = SIMILAR_TITLE.search(message)
    if not (match and WANTS_SUGGESTION.search(message)):
        return None
    title = re.sub(r"\s+(?:anime|manga|movie|series|show)$", "", match.group("title").strip(), flags=re.I)
    return {"title": title} if title else None


INTENT_PATTERNS = [
    (
        re.compile(
            r"\b(highest rated|top rated|best rated|most rated|top anime|best anime|top movies|best movies|top tv|trending|most popular|what('s| is) popular|what('s| are) (users|people) (rating|watching|saving|adding)|watchlist)\b",
            re.I,
        ),
        "get_content_trends",
        lambda msg: {
            "trend_type": (
                "watchlist"
                if re.search(r"watchlist|saving|adding", msg, re.I)
                else "ratings"
            )
        },
    ),
    (
        re.compile(
            r"\b(latest news|recent news|what('s| is) (happening|new|going on)|today('s| ) news|news about|any news)\b",
            re.I,
        ),
        "get_latest_news",
        lambda msg: {},
    ),
    (
        re.compile(
            r"\b(birthday|born today|whose birthday|character.*birthday|birthday.*today)\b",
            re.I,
        ),
        "get_today_birthdays",
        lambda msg: {},
    ),
    (
        re.compile(
            r"\b(anniversary|anniversaries|on this day|today('s| ) event)\b", re.I
        ),
        "get_today_events",
        lambda msg: {},
    ),
]


def _detect_intent(message: str):
    """Returns (tool_name, tool_args) if a clear intent is detected, else None."""
    similar = _similar_title_args(message)
    if similar:
        return "get_similar_titles", similar
    # "Naruto's first chapter name", "what happens in episode 5", "when did Luffy first
    # use Gear 5": answered exactly by the episode & chapter guide inside query_lore.
    if is_exact_question(message):
        return "query_lore", {"query": message}
    for pattern, tool_name, arg_builder in INTENT_PATTERNS:
        if pattern.search(message):
            return tool_name, arg_builder(message)
    return None


def _tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec(name=fn["name"], description=fn["description"], parameters=fn["parameters"])
        for group in AGENT_TOOLS
        for fn in group["function_declarations"]
    ]


# The chat bubble renders only **bold**, *italics* and `code`, line by line.
FORMAT_RULE = (
    " Format for a chat bubble: short paragraphs and simple bullet lists ('- '), "
    "**bold** for names; no tables, no '#' headings."
)
SYNTHESIS_PROMPT = (
    "You are a helpful entertainment assistant. "
    "The user asked a question and we fetched relevant data from our database. "
    "Synthesize the data into a clear, friendly, conversational response. "
    "If it contains an 'episode & chapter guide', answer from that exact data "
    "(chapter/episode numbers and titles) before any lore passages. "
    "If the data is empty or says 'No data available', say so honestly."
) + FORMAT_RULE
BUSY_ANSWER = "All my AI models are busy or out of their daily free quota right now. Please try again later."
ANSWER_NOW = "You have enough information. Answer the user's question now from the tool results above, without calling more tools."

# Some models (gpt-oss) emit narrow/non-breaking spaces and hyphens that render as no gap.
_PLAIN = str.maketrans({" ": " ", " ": " ", " ": " ", " ": " ", " ": " ", "‑": "-"})


def _clean(text: str) -> str:
    return text.translate(_PLAIN).strip()


def _unique(names: list[str]) -> list[str]:
    return list(dict.fromkeys(names))


async def run_agent(user_message: str) -> dict:
    """
    Run the agentic loop for a user message.
    Returns {"answer": str, "tools_used": list[str], "iterations": int, "model": str | None}
    """
    model = container.chat_model()

    # --- Fast path: obvious intents go straight to their tool ---
    intent = _detect_intent(user_message)
    if intent:
        tool_name, tool_args = intent
        print(f"[agent] intent detected → {tool_name}({tool_args})")
        tool_result = await execute_tool(tool_name, tool_args)
        prompt = (
            f"User question: {user_message}\n\n"
            f"Data from database ({tool_name}):\n{tool_result}\n\n"
            "Please provide a helpful response based on this data."
        )
        try:
            reply = await model.complete(SYNTHESIS_PROMPT, [ChatMessage(role="user", content=prompt)])
            answer, used_model = reply.text or tool_result, reply.provider
        except AllModelsUnavailable:
            # Every model is out of quota: the raw data still answers the question.
            answer, used_model = tool_result, None
        return {"answer": _clean(answer), "tools_used": [tool_name], "iterations": 1, "model": used_model}

    # --- Slow path: tool-calling loop (whichever model is available drives it) ---
    tools = _tool_specs()
    system = AGENT_SYSTEM_PROMPT + FORMAT_RULE
    messages = [ChatMessage(role="user", content=user_message)]
    tools_used: list[str] = []
    seen: dict[str, str] = {}  # "tool(args)" -> result, so a repeated call is not run again
    used_model = None

    for iteration in range(1, MAX_ITERATIONS + 1):
        last = iteration == MAX_ITERATIONS
        if last:  # out of steps: no more tools, the model must answer from what it gathered
            messages.append(ChatMessage(role="user", content=ANSWER_NOW))
        try:
            reply = await model.complete(system, messages, None if last else tools)
        except AllModelsUnavailable:
            return {"answer": BUSY_ANSWER, "tools_used": _unique(tools_used), "iterations": iteration, "model": None}
        used_model = reply.provider

        if not reply.tool_calls or last:  # final answer
            return {
                "answer": _clean(reply.text) or "I couldn't find relevant information.",
                "tools_used": _unique(tools_used),
                "iterations": iteration,
                "model": used_model,
            }

        messages.append(ChatMessage(role="assistant", content=reply.text, tool_calls=reply.tool_calls))
        for call in reply.tool_calls:
            key = f"{call.name}({sorted(call.args.items())})"
            if key in seen:
                result = "You already have this result above. " + ANSWER_NOW
            else:
                tools_used.append(call.name)
                print(f"[agent] {reply.provider} calls tool: {call.name}({call.args})")
                result = seen[key] = await execute_tool(call.name, call.args)
            messages.append(ChatMessage(role="tool", content=result, tool_call_id=call.id, name=call.name))
