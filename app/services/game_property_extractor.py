"""
Extracts game properties from a character's description using Gemini.
Called once per character during ingestion and stored in the DB.
"""
import asyncio
import json
import re

import google.generativeai as genai

from app.config import GEMINI_API_KEY
from app.services.game_properties import GAME_PROPERTIES

# Use gemini-2.0-flash (200 RPD free tier) instead of gemini-2.5-flash-lite
# (20 RPD) — game extraction is a batch job and needs higher quota.
MODEL_NAME = "gemini-2.0-flash"


def _build_extraction_prompt(
    character_name: str,
    description: str,
    gender: str | None,
    anime_ids: list[str],
) -> str:

    properties_list = "\n".join(
        f'  "{key}": "{desc}"'
        for key, desc in GAME_PROPERTIES.items()
    )

    anime_context = ", ".join(anime_ids) if anime_ids else "unknown"

    return f"""You are an anime character analyst. Given character info, determine which properties apply.

CHARACTER NAME: {character_name}
GENDER FROM DB: {gender or "unknown"}
APPEARS IN: {anime_context}
DESCRIPTION: {description or "No description available."}

PROPERTY DEFINITIONS:
{properties_list}

RULES:
1. Return ONLY a JSON object — no markdown, no code fences, no explanation.
2. Include ONLY properties that are TRUE for this character.
3. Use the exact property keys from the definitions above.
4. Be conservative — only include properties you are confident about from the description or character name/context.
5. Always include gender properties (isMale/isFemale) if gender is known.
6. For hair color, use the most common depiction of the character.

Example output:
{{"isMale": true, "isHuman": true, "isNinja": true, "hasBlondeHair": true, "isAlive": false}}"""


def _parse_retry_seconds(error_message: str) -> int:
    """Extract retry delay from 429 error message."""
    match = re.search(r"retry in (\d+)", str(error_message))
    if match:
        return int(match.group(1)) + 2  # add 2s buffer
    return 65  # default: wait 65 seconds


async def extract_game_properties(
    character_name: str,
    description: str | None,
    gender: str | None,
    anime_ids: list[str],
    max_retries: int = 3,
) -> list[str]:
    """
    Returns a list of property keys that apply to this character.
    e.g. ["isMale", "isNinja", "hasBlackHair", "isKonoha"]

    Retries automatically on 429 rate limit errors.
    Returns empty list if Gemini is unavailable or description is missing.
    """

    if not GEMINI_API_KEY:
        return []

    if not description and not character_name:
        return []

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(model_name=MODEL_NAME)

    prompt = _build_extraction_prompt(
        character_name=character_name,
        description=description or "",
        gender=gender,
        anime_ids=anime_ids,
    )

    for attempt in range(max_retries):
        try:
            response = await model.generate_content_async(prompt)
            text = response.text.strip()

            # Strip accidental markdown fences
            if text.startswith("```"):
                text = text.strip("`")
                if text.lower().startswith("json"):
                    text = text[4:].strip()

            data = json.loads(text)

            valid_keys = set(GAME_PROPERTIES.keys())

            return [
                key for key, value in data.items()
                if value is True and key in valid_keys
            ]

        except Exception as e:
            error_str = str(e)

            if "429" in error_str or "quota" in error_str.lower():
                retry_after = _parse_retry_seconds(error_str)

                if attempt < max_retries - 1:
                    print(f"[game_extractor] 429 for '{character_name}' — waiting {retry_after}s before retry {attempt + 2}/{max_retries}")
                    await asyncio.sleep(retry_after)
                    continue
                else:
                    print(f"[game_extractor] 429 quota exhausted for '{character_name}' — skipping (run script again tomorrow)")
                    return []

            print(f"[game_extractor] error for '{character_name}': {e}")
            return []

    return []