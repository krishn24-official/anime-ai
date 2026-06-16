"""
Agentic AI service using Gemini function-calling.

The loop:
  1. Send user message + tool definitions to Gemini
  2. Gemini responds with tool call(s) it wants to make
  3. We execute those tools against our real DB
  4. Send results back to Gemini
  5. Repeat until Gemini produces a final text response (no more tool calls)
"""
import re
import google.generativeai as genai

from app.config import GEMINI_API_KEY
from app.services.agent_tool_definitions import AGENT_TOOLS, AGENT_SYSTEM_PROMPT
from app.services.agent_tools import execute_tool

MAX_ITERATIONS = 5  # safety cap on tool-call rounds

# Intent patterns: map regex → (tool_name, arg_builder)
# These fire BEFORE sending to Gemini, routing obvious queries directly.
INTENT_PATTERNS = [
    (
        re.compile(r"\b(highest rated|top rated|best rated|most rated|top anime|best anime|top movies|best movies|top tv|trending|most popular|what('s| is) popular|what('s| are) (users|people) (rating|watching|saving|adding)|watchlist)\b", re.I),
        "get_content_trends",
        lambda msg: {"trend_type": "watchlist" if re.search(r"watchlist|saving|adding", msg, re.I) else "ratings"},
    ),
    (
        re.compile(r"\b(latest news|recent news|what('s| is) (happening|new|going on)|today('s| ) news|news about|any news)\b", re.I),
        "get_latest_news",
        lambda msg: {},
    ),
    (
        re.compile(r"\b(birthday|born today|whose birthday|character.*birthday|birthday.*today)\b", re.I),
        "get_today_birthdays",
        lambda msg: {},
    ),
    (
        re.compile(r"\b(anniversary|anniversaries|on this day|today('s| ) event)\b", re.I),
        "get_today_events",
        lambda msg: {},
    ),
]


def _detect_intent(message: str):
    """Returns (tool_name, tool_args) if a clear intent is detected, else None."""
    for pattern, tool_name, arg_builder in INTENT_PATTERNS:
        if pattern.search(message):
            return tool_name, arg_builder(message)
    return None


def _build_gemini_tools():
    """Convert our tool definitions dict into Gemini SDK tool objects."""
    return [genai.protos.Tool(
        function_declarations=[
            genai.protos.FunctionDeclaration(
                name=fn["name"],
                description=fn["description"],
                parameters=genai.protos.Schema(
                    type=genai.protos.Type.OBJECT,
                    properties={
                        k: genai.protos.Schema(
                            type=genai.protos.Type.STRING
                            if v.get("type") == "string"
                            else genai.protos.Type.INTEGER,
                            description=v.get("description", ""),
                            enum=v.get("enum", []) or [],
                        )
                        for k, v in fn["parameters"].get("properties", {}).items()
                    },
                    required=fn["parameters"].get("required", []),
                ),
            )
            for fn in tool_group["function_declarations"]
        ]
    ) for tool_group in AGENT_TOOLS]


async def run_agent(user_message: str) -> dict:
    """
    Run the agentic loop for a user message.
    Returns {"answer": str, "tools_used": list[str], "iterations": int}
    """

    if not GEMINI_API_KEY:
        return {
            "answer": "AI agent is not configured. Please set GEMINI_API_KEY.",
            "tools_used": [],
            "iterations": 0,
        }

    genai.configure(api_key=GEMINI_API_KEY)

    # --- Fast path: intent detection ---
    intent = _detect_intent(user_message)
    if intent:
        tool_name, tool_args = intent
        print(f"[agent] intent detected → {tool_name}({tool_args})")

        tool_result = await execute_tool(tool_name, tool_args)

        # Use Gemini only for synthesis (no tools, just summarize the data)
        synthesis_model = genai.GenerativeModel(
            model_name="gemini-2.5-flash-lite",
            system_instruction=(
                "You are a helpful entertainment assistant. "
                "The user asked a question and we fetched relevant data from our database. "
                "Synthesize the data into a clear, friendly, conversational response. "
                "If the data is empty or says 'No data available', say so honestly."
            ),
        )

        synthesis_prompt = (
            f"User question: {user_message}\n\n"
            f"Data from database ({tool_name}):\n{tool_result}\n\n"
            "Please provide a helpful response based on this data."
        )

        try:
            response = await synthesis_model.generate_content_async(synthesis_prompt)
            answer = response.text.strip()
        except Exception as e:
            answer = f"Agent error during synthesis: {e}"

        return {
            "answer": answer,
            "tools_used": [tool_name],
            "iterations": 1,
        }

    # --- Slow path: full Gemini tool-calling loop ---
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash-lite",
        system_instruction=AGENT_SYSTEM_PROMPT,
        tools=_build_gemini_tools(),
    )

    # Conversation history for multi-turn tool calling
    messages = [{"role": "user", "parts": [user_message]}]

    tools_used = []
    iterations = 0

    while iterations < MAX_ITERATIONS:
        iterations += 1

        try:
            response = await model.generate_content_async(messages)
        except Exception as e:
            return {
                "answer": f"Agent error: {e}",
                "tools_used": tools_used,
                "iterations": iterations,
            }

        candidate = response.candidates[0]
        parts = candidate.content.parts

        # Check if Gemini wants to call tools
        tool_call_parts = [p for p in parts if hasattr(p, "function_call") and p.function_call.name]

        if not tool_call_parts:
            # No tool calls — this is the final answer
            final_text = "".join(
                p.text for p in parts if hasattr(p, "text") and p.text
            ).strip()

            # Deduplicate tools_used while preserving order
            seen = set()
            unique_tools = []
            for t in tools_used:
                if t not in seen:
                    seen.add(t)
                    unique_tools.append(t)

            return {
                "answer": final_text or "I couldn't find relevant information.",
                "tools_used": unique_tools,
                "iterations": iterations,
            }

        # Execute all tool calls Gemini requested
        tool_results = []

        for part in tool_call_parts:
            fn = part.function_call
            tool_name = fn.name
            tool_args = dict(fn.args) if fn.args else {}

            tools_used.append(tool_name)
            print(f"[agent] calling tool: {tool_name}({tool_args})")

            result_str = await execute_tool(tool_name, tool_args)

            tool_results.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=tool_name,
                        response={"result": result_str},
                    )
                )
            )

        # Add Gemini's tool-call message + our results to the conversation
        messages.append({"role": "model", "parts": parts})
        messages.append({"role": "user", "parts": tool_results})

    # Safety cap reached
    seen = set()
    unique_tools = []
    for t in tools_used:
        if t not in seen:
            seen.add(t)
            unique_tools.append(t)

    return {
        "answer": "I reached the maximum number of reasoning steps. Please try a simpler question.",
        "tools_used": unique_tools,
        "iterations": iterations,
    }