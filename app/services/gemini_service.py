import json
import os
import threading
from datetime import date

from app.config import GEMINI_API_KEY, GEMINI_MODEL_NAME

try:
    from google import genai
    from google.genai import types
    _client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
except Exception as _e:
    print(f"[gemini_service] Warning: Failed to initialize genai: {_e}")
    genai = None
    types = None
    _client = None

# Hard cap on Gemini calls per day for the chat bot.
# Tune via GEMINI_DAILY_LIMIT if you upgrade.
DAILY_LIMIT = int(os.getenv("GEMINI_DAILY_LIMIT", "180"))

# Separate limit for the news pipeline to avoid competing with the chat bot's quota.
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

    if not _client:
        return None

    context_json = json.dumps(character_context, default=str, indent=2)

    prompt = (
        f"DATABASE DATA:\n{context_json}\n\n"
        f"USER QUESTION: {question}"
    )

    return await _generate_with_fallback(prompt, SYSTEM_PROMPT)


LORE_SYSTEM_PROMPT = (
    "You are an anime and entertainment knowledge assistant.\n"
    "You will be given official narrative lore documents and character data retrieved from our database, "
    "along with a user question.\n\n"
    "STRICT GROUNDING INSTRUCTIONS:\n"
    "1. Answer using ONLY the information provided in the lore documents and database context below.\n"
    "2. Do NOT add names, dates, events, character deaths, or details from your own general knowledge "
    "of this series, even if you know them to be completely accurate — if the provided context does not "
    "mention something, you must NOT include it.\n"
    "3. If the user asks about an event, character, or detail that is NOT mentioned in the provided lore "
    "(such as a specific death, family member, or backstory not covered in the text), state explicitly "
    "that the provided lore documents do not contain that information.\n"
    "4. You may explain the parts of the question that ARE covered by the lore (for example, titan "
    "inheritance mechanics, dates, or restrictions explicitly noted in the text), while being clear "
    "about what the documents state versus what they omit.\n"
    "5. Be direct, conversational, and completely factual to the provided documents."
)


async def _generate_with_fallback(prompt: str, system_instruction: str) -> str | None:
    models_to_try = [GEMINI_MODEL_NAME]
    for m in ["gemini-2.5-flash-lite", "gemini-3.6-flash"]:
        if m not in models_to_try:
            models_to_try.append(m)

    for model_name in models_to_try:
        try:
            response = await _client.aio.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                )
            )
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            print(f"[gemini_service] model {model_name} error: {e}")
            continue

    return None


async def ask_gemini_with_lore(
    question: str,
    lore_context: str,
    character_context: dict | None = None,
) -> str | None:
    """
    Returns an answer synthesized from vector lore context, or None if limits or keys prevent it.
    """
    if not GEMINI_API_KEY:
        return None

    if not _can_call_gemini():
        return None

    if not _client:
        return None

    prompt_parts = [f"OFFICIAL LORE DOCUMENTS:\n{lore_context.strip()}\n"]
    if character_context:
        context_json = json.dumps(character_context, default=str, indent=2)
        prompt_parts.append(f"CHARACTER DATABASE DATA:\n{context_json}\n")

    prompt_parts.append(f"USER QUESTION: {question}")
    prompt = "\n".join(prompt_parts)

    return await _generate_with_fallback(prompt, LORE_SYSTEM_PROMPT)


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

    if not _client:
        return None

    import base64
    try:
        image_bytes = base64.b64decode(image_base64)
        image_part = types.Part.from_bytes(
            data=image_bytes,
            mime_type=image_media_type or "image/jpeg"
        )

        prompt = message or "Identify this anime character and describe them."
        response = await _client.aio.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=[prompt, image_part],
            config=types.GenerateContentConfig(
                system_instruction=IMAGE_SYSTEM_PROMPT,
            )
        )
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

    if not _client:
        return None

    prompt = (
        f"TITLE: {title}\n"
        f"DESCRIPTION: {description or '(none)'}"
    )

    try:
        response = await _client.aio.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=NEWS_SYSTEM_PROMPT,
            )
        )
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


LISTICLE_SYSTEM_PROMPT = (
    "You are a news editor for an entertainment app. "
    "You are given the title of a listicle and a list of items extracted from it. "
    "Write a short, engaging introductory paragraph, followed by the complete list of items formatted as a webpage article body. "
    "DO NOT truncate or skip any items from the provided list. Use markdown formatting (e.g., headings or bold for list items)."
)


async def generate_listicle_article_body(title: str, list_items: list[str], full_content: str = "") -> str:
    """
    Intro paragraph + the full ordered list of items,
    formatted for a webpage article body.
    """
    if not GEMINI_API_KEY or not _can_call_gemini_news() or not _client:
        return ""

    prompt = f"TITLE: {title}\n\nEXTRACTED ITEMS:\n"
    for idx, item in enumerate(list_items, 1):
        prompt += f"{idx}. {item}\n"
        
    if full_content:
        # Pass a truncated version of the full content for context
        prompt += f"\n\nPAGE CONTEXT (TRUNCATED):\n{full_content[:2000]}"

    try:
        response = await _client.aio.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=LISTICLE_SYSTEM_PROMPT,
            )
        )
        return response.text.strip()
    except Exception as e:
        print(f"[gemini_service] listicle body generate error: {e}")
        return ""