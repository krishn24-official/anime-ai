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
    ask_gemini_with_context,
    identify_image,
)


# Map of intent keywords -> relationship name(s) to query.
# sensei/teacher/mentor map to DIFFERENT relationship words in the DB
# (see relationship_inverse_map.py), so each keyword queries its own
# word specifically. "mentor" as a keyword queries all three since it's
# often used generically by users.
TARGET_RELATIONSHIP_INTENTS = {
    "father": ["father"],
    "dad": ["father"],
    "mother": ["mother"],
    "mom": ["mother"],
    "sensei": ["sensei"],
    "teacher": ["teacher"],
    "mentor": ["sensei", "teacher", "mentor"],   # generic -> check all 3
    "wife": ["wife"],
    "husband": ["husband"],
    "son": ["son"],
    "daughter": ["daughter"],
    "brother": ["brother"],
    "sister": ["sister"],
    "grandfather": ["grandfather"],
    "grandmother": ["grandmother"],
    "grandson": ["grandson"],
    "granddaughter": ["granddaughter"],
    "uncle": ["uncle"],
    "aunt": ["aunt"],
    "nephew": ["nephew"],
    "niece": ["niece"],
    "cousin": ["cousin"],
    "crush": ["crush"],
    "classmate": ["classmate"],
    "teammate": ["teammate"],

    # In-laws
    "father_in_law": ["father_in_law"],
    "mother_in_law": ["mother_in_law"],
    "son_in_law": ["son_in_law"],
    "daughter_in_law": ["daughter_in_law"],
    "brother_in_law": ["brother_in_law"],
    "sister_in_law": ["sister_in_law"],
    "uncle_in_law": ["uncle_in_law"],
    "aunt_in_law": ["aunt_in_law"],
    "nephew_in_law": ["nephew_in_law"],
    "niece_in_law": ["niece_in_law"],

    # Step-family
    "stepfather": ["stepfather"],
    "stepmother": ["stepmother"],
    "stepson": ["stepson"],
    "stepdaughter": ["stepdaughter"],
    "stepbrother": ["stepbrother"],
    "stepsister": ["stepsister"],
}


def extract_character_query(message: str) -> str:
    text = message.lower().strip()
    text = text.replace("\u2019", "'").replace("\u2018", "'")

    text = re.sub(
        r"^(who is|who's|whos|what is|whats|tell me about|show me|get)\s+",
        "",
        text
    )

    text = text.strip("? ").strip()

    # Pattern 1: [relationship] of [character] or [relationship] members of [character]
    rel_words_pattern = (
        r"(father|dad|mother|mom|sensei|teacher|mentor|wife|husband|"
        r"son|daughter|brother|sister|grandfather|grandmother|"
        r"grandson|granddaughter|uncle|aunt|nephew|niece|cousin|"
        r"crush|classmate|teammate|family|team)"
    )

    match = re.match(
        rf"^{rel_words_pattern}s?(\s+member)?s?\s+of\s+(.+)$",
        text
    )

    if match:
        return match.group(3).strip()

    match = re.match(
        r"^does\s+(.+?)\s+have\s+(?:a|an)?\s*\w+$",
        text
    )

    if match:
        return match.group(1).strip()

    match = re.match(
        r"^does\s+(.+?)\s+have\s+\w+$",
        text
    )

    if match:
        return match.group(1).strip()

    # Pattern 2: [character]'s [relationship] or [character]'a [relationship] [member(s)]
    words_to_strip = [
        "family members", "family member", "family",
        "team members", "team member", "team",
        "father", "dad", "mother", "mom", "sensei", "teacher", "mentor",
        "wife", "husband", "son", "daughter", "brother", "sister",
        "grandfather", "grandmother", "grandson", "granddaughter",
        "uncle", "aunt", "nephew", "niece", "cousin", "crush", "classmate", "teammate"
    ]

    cleaned = text
    for word in words_to_strip:
        pattern = rf"\b{word}s?\b$"
        if re.search(pattern, cleaned):
            cleaned = re.sub(pattern, "", cleaned).strip()
            break

    # Strip possessive suffixes like "'s", "'a", or ending "'"
    cleaned = re.sub(r"['’][sa]$", "", cleaned)
    cleaned = re.sub(r"['’]$", "", cleaned)
    cleaned = cleaned.strip()

    return cleaned


def extract_two_character_query(message: str):
    text = message.lower().strip()
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.strip("? ").strip()

    match = re.search(
        r"relationship between\s+(.+?)\s+and\s+(.+)$",
        text
    )

    if match:
        return match.group(1).strip(), match.group(2).strip()

    match = re.search(
        r"^(?:are|is)\s+(.+?)\s+and\s+(.+?)\s+\w+$",
        text
    )

    if match:
        return match.group(1).strip(), match.group(2).strip()

    match = re.search(
        r"^is\s+(.+?)\s+(.+?)'s\s+\w+$",
        text
    )

    if match:
        return match.group(1).strip(), match.group(2).strip()

    return None


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


def detect_intent(message: str):

    message = message.lower()

    # Normalize natural phrasing of in-law/step relations to match our
    # underscore-joined keys, e.g. "father-in-law" / "father in law" -> "father_in_law"
    message = re.sub(
        r"\b(father|mother|son|daughter|brother|sister|uncle|aunt|nephew|niece)"
        r"[\s-]+in[\s-]+law\b",
        r"\1_in_law",
        message
    )

    # Check longest keywords first so e.g. "father_in_law" matches before
    # the shorter "father" substring collision.
    for keyword in sorted(TARGET_RELATIONSHIP_INTENTS, key=len, reverse=True):
        if keyword in message:
            return keyword

    if "family" in message:
        return "family"

    if "team" in message:
        return "team"

    return "unknown"


async def process_chat_message(
    message: str,
    image_base64: str | None = None,
    image_media_type: str = "image/jpeg",
):
    # --- Image recognition mode ---
    # --- Image recognition mode ---
    if image_base64:
        result = await identify_image(
            message=message,
            image_base64=image_base64,
            image_media_type=image_media_type,
        )

        if result:
            return {"answer": result}

        return {
            "answer": (
                "I received your image but couldn't analyze it right now "
                "(daily AI limit reached or service unavailable). "
                "Try describing the character in text and I'll help from my database."
            )
        }

    # --- Two-character relationship questions ---
    two_char = extract_two_character_query(message)

    if two_char:

        name_a, name_b = two_char

        char_a = await find_character(name_a)
        char_b = await find_character(name_b)

        if char_a and char_b:
            return await describe_relationship_between(char_a, char_b)

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

    if intent in TARGET_RELATIONSHIP_INTENTS:

        relationship_names = TARGET_RELATIONSHIP_INTENTS[intent]

        all_results = []
        for relationship_name in relationship_names:
            results = await get_relationships_by_target(
                character["_id"],
                relationship=relationship_name
            )
            all_results.extend(results)

        if not all_results:
            return {
                "answer":
                f"I couldn't find a {intent} for {character['name']}."
            }

        enriched = await enrich_relationships_by_source(all_results)

        # Pair each name with the specific relationship word used
        # (sensei vs teacher vs mentor), so the answer is precise
        # even when multiple words were searched.
        labeled = [
            f"{r['target']['name']} ({r['relationship']})"
            if len(relationship_names) > 1 else r["target"]["name"]
            for r in enriched if r["target"]
        ]

        return {
            "answer":
            f"{character['name']}'s {intent} is {', '.join(labeled)}."
        }

    if intent == "family":

        details = await build_character_context(character) or {}

        family_names = [
            member["target"]["name"]
            for member in details.get("family", [])
            if member.get("target")
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

        details = await build_character_context(character) or {}

        team_names = [
            member["target"]["name"]
            for member in details.get("team", [])
            if member.get("target")
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

    # intent == "unknown" — try Gemini, fall back to local data
    gemini_answer = await ask_gemini_with_context(
        message,
        await build_character_context(character)
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