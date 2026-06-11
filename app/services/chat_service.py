import re

from app.repositories.chat_repository import (
    find_character
)

from app.repositories.relationship_repository import (
    get_relationships_by_type,
    get_relationships_by_target
)

from app.services.character_service import (
    enrich_relationships_by_source,
    enrich_relationships
)

from app.services.chat_context_service import (
    build_character_context
)

from app.services.gemini_service import (
    ask_gemini_with_context
)


# Map of intent keywords -> (relationship name, type)
# These are looked up via get_relationships_by_target:
# i.e. "X's father" = relationship where target_id=X, relationship="father"
TARGET_RELATIONSHIP_INTENTS = {
    "father": "father",
    "dad": "father",
    "mother": "mother",
    "mom": "mother",
    "sensei": "mentor",
    "teacher": "mentor",
    "mentor": "mentor",
    "wife": "wife",
    "husband": "husband",
    "son": "son",
    "daughter": "daughter",
    "brother": "brother",
    "sister": "sister",
    "grandfather": "grandfather",
    "grandmother": "grandmother",
    "grandson": "grandson",
    "granddaughter": "granddaughter",
    "uncle": "uncle",
    "aunt": "aunt",
    "nephew": "nephew",
    "niece": "niece",
    "cousin": "cousin",
    "crush": "crush",
    "classmate": "classmate",
    "teammate": "teammate",
}


def extract_character_query(message: str) -> str:
    """
    Pulls the likely character name out of a question like
    "who is naruto's father" -> "naruto"
    or "naruto's father" -> "naruto"
    """

    text = message.lower().strip()

    # normalize curly apostrophes to straight ones
    text = text.replace("\u2019", "'").replace("\u2018", "'")

    # remove leading question phrases
    text = re.sub(
        r"^(who is|who's|whos|what is|whats|tell me about)\s+",
        "",
        text
    )

    text = text.strip("? ").strip()

    # remove possessive + trailing relation word(s)
    # e.g. "naruto's father" -> "naruto"
    if "'s" in text:
        text = text.split("'s")[0]
    else:
        # fallback: try to drop a trailing known relation word
        for word in (
            "father", "dad", "mother", "mom", "sensei", "teacher",
            "mentor", "wife", "husband", "son", "daughter",
            "brother", "sister", "grandfather", "grandmother",
            "grandson", "granddaughter", "uncle", "aunt",
            "nephew", "niece", "cousin", "crush", "classmate",
            "teammate", "family", "team"
        ):
            if text.endswith(word):
                text = text[: -len(word)]
                break

    text = text.strip("? ").strip()

    return text


def detect_intent(message: str):

    message = message.lower()

    for keyword in TARGET_RELATIONSHIP_INTENTS:
        if keyword in message:
            return keyword

    if "family" in message:
        return "family"

    if "team" in message:
        return "team"

    return "unknown"


async def process_chat_message(
    message: str
):

    name_query = extract_character_query(message)

    print(f"[chat] message={message!r} name_query={name_query!r}")

    if not name_query:

        return {
            "answer":
            "I couldn't understand which character you're asking about."
        }

    character = await find_character(name_query)

    if not character:

        return {
            "answer":
            f"I couldn't find a character matching '{name_query}'."
        }

    intent = detect_intent(message)

    # father / mother / sensei -> look for relationships
    # where THIS character is the target
    if intent in TARGET_RELATIONSHIP_INTENTS:

        relationship_name = TARGET_RELATIONSHIP_INTENTS[intent]

        results = await get_relationships_by_target(
            character["_id"],
            relationship=relationship_name
        )

        if not results:

            return {
                "answer":
                f"I couldn't find a {intent} for "
                f"{character['name']}."
            }

        enriched = await enrich_relationships_by_source(results)

        names = [r["target"]["name"] for r in enriched if r["target"]]

        return {
            "answer":
            f"{character['name']}'s {intent} is "
            f"{', '.join(names)}."
        }

    # family / team -> use full context as before
    details = await build_character_context(character["_id"])

    if intent == "family":

        family_names = [
            member["target"]["name"]
            for member in details["family"]
            if member["target"]
        ]

        if not family_names:
            return {
                "answer":
                f"No family members found for {character['name']}."
            }

        return {
            "answer":
            f"Family members of {character['name']}: "
            f"{', '.join(family_names)}"
        }

    if intent == "team":

        team_names = [
            member["target"]["name"]
            for member in details["team"]
            if member["target"]
        ]

        if not team_names:
            return {
                "answer":
                f"No team members found for {character['name']}."
            }

        return {
            "answer":
            f"Team members of {character['name']}: "
            f"{', '.join(team_names)}"
        }

    if intent == "unknown":

        # Try Gemini first (only if API key set and under daily cap).
        # If it returns None, fall back to local description-based answer.
        gemini_answer = await ask_gemini_with_context(
            message,
            await build_character_context(character["_id"])
        )

        if gemini_answer:
            return {"answer": gemini_answer}

        description = character.get("description")
        role = character.get("role")
        affiliations = character.get("affiliations") or []

        parts = []

        if description:
            parts.append(description)

        if role:
            parts.append(f"Role: {role}.")

        if affiliations:
            parts.append(f"Affiliations: {', '.join(affiliations)}.")

        if parts:
            return {
                "answer":
                f"{character['name']} - " + " ".join(parts)
            }

    return {
        "answer":
        f"I found {character['name']} but couldn't determine "
        f"the question type."
    }