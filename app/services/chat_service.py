import re

from app.repositories.chat_repository import (
    find_character
)

from app.repositories.relationship_repository import (
    get_relationships_by_type,
    get_relationships_by_target,
    get_relationship_between
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

    # "<relation> of <name>" -> <name>  e.g. "sister of naruto" -> "naruto"
    match = re.match(
        r"^(father|dad|mother|mom|sensei|teacher|mentor|wife|husband|"
        r"son|daughter|brother|sister|grandfather|grandmother|"
        r"grandson|granddaughter|uncle|aunt|nephew|niece|cousin|"
        r"crush|classmate|teammate|family|team)s?\s+of\s+(.+)$",
        text
    )

    if match:
        return match.group(2).strip()

    # "does X have a/an <relation>" -> X
    match = re.match(
        r"^does\s+(.+?)\s+have\s+(?:a|an)?\s*\w+$",
        text
    )

    if match:
        return match.group(1).strip()

    # "does X have <relation>" (plural, no article) -> X
    match = re.match(
        r"^does\s+(.+?)\s+have\s+\w+$",
        text
    )

    if match:
        return match.group(1).strip()

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


def extract_two_character_query(message: str):
    """
    Detects two-character questions and returns (name_a, name_b) or None.

    Handles patterns like:
      "are naruto and sasuke friends?"
      "what is the relationship between naruto and sasuke"
      "relationship between naruto and sasuke?"
      "is naruto sasuke's rival?"
    """

    text = message.lower().strip()
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.strip("? ").strip()

    # "relationship between X and Y"
    match = re.search(
        r"relationship between\s+(.+?)\s+and\s+(.+)$",
        text
    )

    if match:
        return match.group(1).strip(), match.group(2).strip()

    # "are X and Y <something>" / "is X and Y <something>"
    match = re.search(
        r"^(?:are|is)\s+(.+?)\s+and\s+(.+?)\s+\w+$",
        text
    )

    if match:
        return match.group(1).strip(), match.group(2).strip()

    # "is X Y's <relation>" e.g. "is naruto sasuke's rival"
    match = re.search(
        r"^is\s+(.+?)\s+(.+?)'s\s+\w+$",
        text
    )

    if match:
        return match.group(1).strip(), match.group(2).strip()

    return None


TWO_CHAR_RELATION_LABELS = {
    "father": "child of",
    "mother": "child of",
    "son": "parent of",
    "daughter": "parent of",
    "brother": "sibling of",
    "sister": "sibling of",
    "wife": "spouse of",
    "husband": "spouse of",
    "mentor": "student of",
    "rival": "rival of",
    "crush": "has a crush on",
    "teammate": "teammate of",
    "classmate": "classmate of",
    "friend": "friend of",
    "best_friend": "best friend of",
}


SYMMETRIC_RELATIONS = {
    "teammate", "classmate", "friend", "best_friend",
    "rival", "cousin", "sibling", "brother", "sister",
    "brother_in_law", "sister_in_law"
}


async def describe_relationship_between(char_a, char_b):

    relationships = await get_relationship_between(
        char_a["_id"],
        char_b["_id"]
    )

    if not relationships:

        return {
            "answer":
            f"I couldn't find any known relationship between "
            f"{char_a['name']} and {char_b['name']}."
        }

    sentences = []
    seen_symmetric = set()

    for rel in relationships:

        relation_word = rel["relationship"]

        if relation_word in SYMMETRIC_RELATIONS:

            if relation_word in seen_symmetric:
                continue

            seen_symmetric.add(relation_word)

            sentences.append(
                f"{char_a['name']} and {char_b['name']} are "
                f"{relation_word.replace('_', ' ')}s"
            )

            continue

        if rel["source_id"] == char_a["_id"]:
            subject, other = char_a["name"], char_b["name"]
        else:
            subject, other = char_b["name"], char_a["name"]

        sentences.append(
            f"{subject} is {other}'s {relation_word.replace('_', ' ')}"
        )

    return {
        "answer": ". ".join(sentences) + "."
    }

    message = message.lower()

    for keyword in TARGET_RELATIONSHIP_INTENTS:
        if keyword in message:
            return keyword

    if "family" in message:
        return "family"

    if "team" in message:
        return "team"

    return "unknown"


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

    # --- Two-character relationship questions ---
    two_char = extract_two_character_query(message)

    if two_char:

        name_a, name_b = two_char

        char_a = await find_character(name_a)
        char_b = await find_character(name_b)

        if char_a and char_b:
            return await describe_relationship_between(char_a, char_b)

        # If one or both names not found, fall through to
        # single-character handling below (better than failing outright)

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