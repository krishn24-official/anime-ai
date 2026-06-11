import json
import os
import threading
from datetime import date

import google.generativeai as genai

from app.config import GEMINI_API_KEY


genai.configure(api_key=GEMINI_API_KEY)

MODEL_NAME = "gemini-2.5-flash-lite"

# Hard cap on Gemini calls per day. Tune this to your free-tier limit.
# Once exceeded, calls are skipped (no exception, no charge risk).
DAILY_LIMIT = int(os.getenv("GEMINI_DAILY_LIMIT", "50"))


SYSTEM_PROMPT = (
    "You are an anime knowledge assistant. "
    "You will be given JSON data about an anime character from a database, "
    "and a user question. "
    "Answer the question using ONLY the information in the provided JSON data. "
    "Be concise and conversational. "
    "If the JSON data does not contain enough information to answer the "
    "question, say so honestly instead of guessing or using outside knowledge."
)


# --- Simple in-memory daily usage counter ---
# NOTE: resets on server restart and is per-process (not shared across
# multiple server instances). Good enough for a single-instance dev/personal
# project. For production, move this to Redis/DB.
_lock = threading.Lock()
_usage = {"date": date.today().isoformat(), "count": 0}


def _can_call_gemini() -> bool:

    with _lock:

        today = date.today().isoformat()

        if _usage["date"] != today:
            _usage["date"] = today
            _usage["count"] = 0

        if _usage["count"] >= DAILY_LIMIT:
            return False

        _usage["count"] += 1
        return True


def get_gemini_usage() -> dict:

    with _lock:
        return {
            "date": _usage["date"],
            "count": _usage["count"],
            "limit": DAILY_LIMIT
        }


async def ask_gemini_with_context(question: str, character_context: dict):
    """
    Returns the AI answer, or None if the daily limit has been reached
    or GEMINI_API_KEY is not configured. Caller should handle None by
    falling back to a local answer.
    """

    if not GEMINI_API_KEY:
        return None

    if not _can_call_gemini():
        return None

    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=SYSTEM_PROMPT
    )

    context_json = json.dumps(character_context, default=str, indent=2)

    prompt = (
        f"DATABASE DATA:\n{context_json}\n\n"
        f"USER QUESTION: {question}"
    )

    try:
        response = await model.generate_content_async(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"[gemini_service] error: {e}")
        return None