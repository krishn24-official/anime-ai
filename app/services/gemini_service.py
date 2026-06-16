import json
import os
import threading
from datetime import date

import google.generativeai as genai

from app.config import GEMINI_API_KEY


genai.configure(api_key=GEMINI_API_KEY)

MODEL_NAME = "gemini-2.5-flash-lite"

# Hard cap on Gemini calls per day for the chat bot (gemini-2.5-flash-lite
# free tier = 20 RPD). Tune via GEMINI_DAILY_LIMIT if you upgrade.
DAILY_LIMIT = int(os.getenv("GEMINI_DAILY_LIMIT", "18"))

# Separate model + limit for the news pipeline. gemini-2.0-flash has a
# much higher free-tier daily limit (200 RPD) than gemini-2.5-flash-lite
# (20 RPD), and using a separate model avoids competing with the chat
# bot's quota.
NEWS_MODEL_NAME = "gemini-2.0-flash"
NEWS_DAILY_LIMIT = int(os.getenv("GEMINI_NEWS_DAILY_LIMIT", "180"))


SYSTEM_PROMPT = (
    "You are an anime knowledge assistant. "
    "You will be given JSON data about an anime character from a database, "
    "and a user question. "
    "Answer the question using ONLY the information in the provided JSON data. "
    "Be concise and conversational. "
    "If the JSON data does not contain enough information to answer the "
    "question, say so honestly instead of guessing or using outside knowledge."
)


# --- Simple in-memory daily usage counters (separate for chat vs news) ---
# NOTE: resets on server restart and is per-process (not shared across
# multiple server instances). Good enough for a single-instance dev/personal
# project. For production, move this to Redis/DB.
_lock = threading.Lock()
_usage = {"date": date.today().isoformat(), "count": 0}
_news_usage = {"date": date.today().isoformat(), "count": 0}


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


def _can_call_gemini_news() -> bool:

    with _lock:

        today = date.today().isoformat()

        if _news_usage["date"] != today:
            _news_usage["date"] = today
            _news_usage["count"] = 0

        if _news_usage["count"] >= NEWS_DAILY_LIMIT:
            return False

        _news_usage["count"] += 1
        return True


def get_gemini_usage() -> dict:

    with _lock:
        return {
            "date": _usage["date"],
            "count": _usage["count"],
            "limit": DAILY_LIMIT
        }


def get_gemini_news_usage() -> dict:

    with _lock:
        return {
            "date": _news_usage["date"],
            "count": _news_usage["count"],
            "limit": NEWS_DAILY_LIMIT
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


IMAGE_SYSTEM_PROMPT = (
    "You are an anime knowledge assistant. Analyze the provided image and answer "
    "the user's question about it. Identify the character, anime, and provide "
    "interesting context."
)


async def identify_image(message: str, image_base64: str, image_media_type: str | None = None) -> str | None:
    """
    Returns the image analysis from Gemini, or None if limits or keys prevent it.
    """
    if not GEMINI_API_KEY:
        return None

    if not _can_call_gemini():
        return None

    import base64
    try:
        image_bytes = base64.b64decode(image_base64)
        image_part = {
            "mime_type": image_media_type or "image/jpeg",
            "data": image_bytes
        }

        model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            system_instruction=IMAGE_SYSTEM_PROMPT
        )
        prompt = message or "Identify this anime character and describe them."
        response = await model.generate_content_async([prompt, image_part])
        return response.text.strip()
    except Exception as e:
        print(f"[gemini_service] image identify error: {e}")
        return None


NEWS_SYSTEM_PROMPT = (
    "You are a news editor for an entertainment app covering Anime, Games, "
    "Movies, and TV Series. For each article given (title + optional "
    "description), respond with ONLY a JSON object (no markdown, no code "
    "fences) with these keys:\n"
    '  "category": one of "Anime", "Games", "Movies", "TV Series", or '
    '"Other" if it does not fit any of these,\n'
    '  "summary": a clean, neutral 1-2 sentence summary (max 240 characters) '
    "for a news card, written in your own words.\n"
    "If the article is not relevant to anime, games, movies, or TV series "
    "entertainment news, set category to \"Other\"."
)


async def categorize_and_summarize_news(title: str, description: str = ""):
    """
    Returns {"category": str, "summary": str} or None if the daily limit
    has been reached or GEMINI_API_KEY is not configured. Caller should
    handle None with a fallback (e.g. category="Other", summary=description).
    """

    if not GEMINI_API_KEY:
        return None

    if not _can_call_gemini_news():
        return None

    model = genai.GenerativeModel(
        model_name=NEWS_MODEL_NAME,
        system_instruction=NEWS_SYSTEM_PROMPT
    )

    prompt = (
        f"TITLE: {title}\n"
        f"DESCRIPTION: {description or '(none)'}"
    )

    try:
        response = await model.generate_content_async(prompt)
        text = response.text.strip()

        # Strip accidental markdown code fences
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()

        data = json.loads(text)

        category = data.get("category", "Other")
        summary = data.get("summary", "")

        if category not in ("Anime", "Games", "Movies", "TV Series", "Other"):
            category = "Other"

        return {"category": category, "summary": summary.strip()}

    except Exception as e:
        print(f"[gemini_service] news categorize error: {e}")
        return None