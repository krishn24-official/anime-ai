import difflib
import re

from app.repositories.home_repository import get_today_birthdays
from app.repositories.news_repository import get_latest_news
from app.repositories.rating_repository import get_top_rated

from app.repositories.chat_repository import (
    find_character,
    find_character_candidates,
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

# Flat list of all recognised intent keywords — used for fuzzy matching.
_ALL_INTENT_KEYWORDS = list(TARGET_RELATIONSHIP_INTENTS.keys()) + ["family", "team"]


def fuzzy_match_intent(word: str) -> str | None:
    """
    Returns the closest intent keyword if similarity >= 80%, else None.
    Handles typos like 'taemmates' -> 'teammate', 'clasmetes' -> 'classmate'.
    """
    matches = difflib.get_close_matches(word, _ALL_INTENT_KEYWORDS, n=1, cutoff=0.8)
    return matches[0] if matches else None


def extract_character_query(message: str) -> str:
    text = message.lower().strip()
    text = text.replace("\u2019", "'").replace("\u2018", "'")

    text = re.sub(
        r"^(who is|who's|whos|what is|whats|tell me about|show me|get)\s+",
        "",
        text
    )

    text = re.sub(r"^(character|actor|movie|anime|tv series):\s*", "", text)
    
    # Strip media keywords to leave just the title
    text = re.sub(r"\b(the |a |an )?(anime|movie|tv show|tv series|series)s?\b", "", text)
    
    text = text.strip("? :").strip()

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

    # Fuzzy fallback: check each word in the message for a close intent match.
    for word in message.split():
        matched = fuzzy_match_intent(word)
        if matched:
            return matched

    return "unknown"


async def process_chat_message(
    message: str,
    image_base64: str | None = None,
    image_media_type: str = "image/jpeg",
):
    msg_lower = message.lower()

    # --- Fast-path intercepts: Bypass Gemini for standard platform queries ---

    # 1. News for birthday characters
    if "news" in msg_lower and "birthday" in msg_lower:
        birthdays = await get_today_birthdays()
        if not birthdays:
            return {"answer": "There are no character birthdays today, so there's no news about them!"}

        bday_names = [b.get("name") for b in birthdays if b.get("name")]
        news_articles = await get_latest_news(limit=20)
        relevant_news = []
        for article in news_articles:
            text_to_search = (article.get("title", "") + " " + article.get("summary", "")).lower()
            if any(name.lower() in text_to_search for name in bday_names):
                relevant_news.append(article)

        if not relevant_news:
            return {
                "answer": f"Today's birthdays are: {', '.join(bday_names)}! But I couldn't find any recent news specifically about them."
            }

        news_text = "\n\n".join([f"**{a.get('title')}**\n{a.get('summary', '')}" for a in relevant_news[:3]])
        return {
            "answer": f"Yes! Here is the latest news for today's birthday characters ({', '.join(bday_names)}):\n\n{news_text}"
        }

    # 1.5. Attribute QA Engine
    from app.services.attribute_query_service import detect_attribute_intent
    attr_intent = detect_attribute_intent(message)
    if attr_intent and not image_base64:
        ent_name, attr_key, explicit_type = attr_intent
        types_list = [explicit_type] if explicit_type else ["character", "anime", "movie", "tv_series"]
        
        from app.repositories.relationship_repository import search_relationship_entities
        candidates = await search_relationship_entities(ent_name, limit=5, types_list=types_list)
        
        if not candidates:
            return {"answer": f"I couldn't find anything matching '{ent_name}' to look up '{attr_key.replace('_', ' ')}'."}
            
        if len(candidates) == 1:
            m = candidates[0]
            m_type = m["entity_type"]
            from app.services.attribute_formatter import format_attribute_response
            
            from app.db.mongo import get_db
            db = get_db()
            
            full_doc = None
            if m_type == "anime":
                full_doc = await db["anime"].find_one({"_id": m["id"]})
            elif m_type == "movie":
                full_doc = await db["movies"].find_one({"_id": m["id"]})
            elif m_type == "tv_series":
                full_doc = await db["tv_series"].find_one({"_id": m["id"]})
            elif m_type == "character":
                full_doc = await db["characters"].find_one({"_id": m["id"]})
                
            if full_doc:
                return {"answer": format_attribute_response(full_doc, m_type, attr_key)}
            else:
                return {"answer": f"Could not retrieve full details for {m['name']}."}
        else:
            def format_media_type(t: str):
                if t == "tv_series": return "TV Series"
                return t.title()

            disambiguation_options = []
            for c in candidates:
                disambig_str = f"{format_media_type(c['entity_type'])}: {c['name']}"
                disambig_str += f" - {attr_key.replace('_', ' ')}"
                disambiguation_options.append(disambig_str)
                
            return {
                "answer": (
                    f"I found multiple matches for '{ent_name}'. "
                    f"Which one did you mean for '{attr_key.replace('_', ' ')}'?"
                ),
                "disambiguation": disambiguation_options,
                "name_query": ent_name,
                "original_message": message,
            }

    # 2. Birthdays
    if "birthday" in msg_lower:
        birthdays = await get_today_birthdays()
        
        from app.repositories.actors_repository import get_birthdays_by_date_range
        from datetime import datetime
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        actor_birthdays = await get_birthdays_by_date_range(today_str, today_str)

        if not birthdays and not actor_birthdays:
            return {"answer": "There are no character or actor birthdays today."}
        
        names = [b.get("name") for b in birthdays if b.get("name")]
        actor_names = [a.get("name") for a in actor_birthdays if a.get("name")]
        
        answer_parts = []
        if names:
            answer_parts.append(f"The following characters are celebrating their birthday today: **{', '.join(names)}**!")
        if actor_names:
            answer_parts.append(f"The following actors are celebrating their birthday today: **{', '.join(actor_names)}**!")
            
        return {"answer": "\n\n".join(answer_parts)}

    # 3. Latest News
    if "news" in msg_lower:
        articles = await get_latest_news(limit=3)
        if not articles:
            return {"answer": "I couldn't find any recent anime news."}
        news_text = "\n\n".join([f"**{a.get('title')}**\n{a.get('summary', '')[:150]}..." for a in articles])
        return {"answer": f"Here is the latest anime news:\n\n{news_text}"}

    # 4. Recommendations
    if "recommend" in msg_lower or "must-watch" in msg_lower:
        top = await get_top_rated("anime", limit=3)
        if not top:
            return {"answer": "I don't have any anime recommendations right now."}
        recs = "\n".join([f"• **{a.get('title', {}).get('english') or a.get('title', {}).get('romaji')}**" for a in top])
        return {"answer": f"Here are some highly-rated anime I recommend watching:\n\n{recs}"}


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

    # Detect if user clicked a disambiguation chip (e.g. "Actor: Hrithik Roshan")
    temp_text = re.sub(
        r"^(who is|who's|whos|what is|whats|tell me about|show me|get)\s+",
        "",
        message.lower().strip()
    )
    
    forced_scope = None
    if temp_text.startswith("character:"): forced_scope = "character"
    elif temp_text.startswith("actor:"): forced_scope = "actor"
    elif temp_text.startswith("movie:"): forced_scope = "movie"
    elif temp_text.startswith("tv series:"): forced_scope = "tv_series"
    elif temp_text.startswith("anime:"): forced_scope = "anime"
    else:
        # Detect scope from natural language
        if re.search(r"\b(movie|film)s?\b", temp_text): forced_scope = "movie"
        elif re.search(r"\b(anime)s?\b", temp_text): forced_scope = "anime"
        elif re.search(r"\b(tv show|tv series|series)\b", temp_text): forced_scope = "tv_series"
        elif re.search(r"\b(actor|actress|director|producer|writer)\b", temp_text): forced_scope = "actor"


    name_query = extract_character_query(message)

    print(f"[chat] message={message!r} name_query={name_query!r} scope={forced_scope!r}")

    if not name_query:
        return {
            "answer":
            "I couldn't understand which character you're asking about."
        }

    candidates = []
    if forced_scope in (None, "character"):
        candidates = await find_character_candidates(name_query)

    media_candidates = []
    if forced_scope in (None, "anime", "movie", "tv_series"):
        from app.repositories.relationship_repository import search_relationship_entities
        types_list = [forced_scope] if forced_scope else ["anime", "movie", "tv_series"]
        media_candidates = await search_relationship_entities(name_query, limit=15, types_list=types_list)

    actor_candidates = []
    if forced_scope in (None, "actor"):
        from app.repositories.actors_repository import find_actor_candidates
        actor_candidates = await find_actor_candidates(name_query)

    total_candidates = len(candidates) + len(media_candidates) + len(actor_candidates)

    if total_candidates == 0:
        # Try a general query before giving up
        gemini_answer = await ask_gemini_with_context(message, {})
        if gemini_answer:
            return {"answer": gemini_answer}
        return {
            "answer":
            f"I couldn't find anything matching '{name_query}'."
        }

    if total_candidates > 1:
        exact_character_matches = [c for c in candidates if c["name"].lower() == name_query.lower()]
        exact_media_matches = [m for m in media_candidates if m["name"].lower() == name_query.lower()]
        exact_actor_matches = [a for a in actor_candidates if a["name"].lower() == name_query.lower()]

        # If the user explicitly forced a scope (like from clicking a disambiguation chip) 
        # and there is an exact match for that scope, bypass disambiguation and select it immediately.
        if forced_scope == "character" and len(exact_character_matches) >= 1:
            candidates = [exact_character_matches[0]]
            media_candidates, actor_candidates = [], []
            total_candidates = 1
        elif forced_scope in ("anime", "movie", "tv_series") and len(exact_media_matches) >= 1:
            type_matches = [m for m in exact_media_matches if m["entity_type"] == forced_scope]
            if type_matches:
                media_candidates = [type_matches[0]]
                candidates, actor_candidates = [], []
                total_candidates = 1
        elif forced_scope == "actor" and len(exact_actor_matches) >= 1:
            actor_candidates = [exact_actor_matches[0]]
            candidates, media_candidates = [], []
            total_candidates = 1
            
    if total_candidates > 1:
        # Score character candidates
        best_candidate = None
        highest_score = 0.0

        if candidates:
            query_words = set(re.sub(r"[^\w\s]", "", name_query.lower()).split())

            for c in candidates:
                cand_words = set(re.sub(r"[^\w\s]", "", c["name"].lower()).split())
                max_word_score = 0.0
                
                if query_words.intersection(cand_words):
                    max_word_score = 1.0
                else:
                    for qw in query_words:
                        for cw in cand_words:
                            score = difflib.SequenceMatcher(None, qw, cw).ratio()
                            if score > max_word_score:
                                max_word_score = score
                
                if max_word_score > highest_score:
                    highest_score = max_word_score
                    best_candidate = c

        if not exact_character_matches and not exact_media_matches and not exact_actor_matches and len(name_query.split()) >= 3:
            gemini_answer = await ask_gemini_with_context(message, {})
            if gemini_answer:
                return {"answer": gemini_answer}

        if highest_score > 0.90 and best_candidate and not exact_media_matches and not exact_actor_matches and not (actor_candidates and highest_score < 1.0):
            character = best_candidate
        else:
            def format_media_type(t: str):
                if t == "tv_series": return "TV Series"
                return t.title()

            media_options = [f"{format_media_type(m['entity_type'])}: {m['name']}" for m in media_candidates]
            char_options = [f"Character: {c['name']}" for c in candidates]
            actor_options = [f"Actor: {a['name']}" for a in actor_candidates]
            
            return {
                "answer": (
                    f"I found multiple matches for '{name_query}'. "
                    "Which one did you mean?"
                ),
                "disambiguation": char_options + actor_options + media_options,
                "name_query": name_query,
                "original_message": message,
            }
    else:
        # total_candidates == 1
        if candidates:
            character = candidates[0]
        elif actor_candidates:
            from app.services.actors_service import fetch_actor_filmography
            from app.services.actor_profile_formatter import format_actor_profile
            actor = actor_candidates[0]
            kf = await fetch_actor_filmography(actor)
            return {"answer": format_actor_profile(actor, kf)}
        else:
            # We found exactly 1 media candidate, fake a fast-path routing
            m = media_candidates[0]
            m_type = m["entity_type"]
            from app.services.content_profile_formatter import format_content_profile
            if m_type == "anime":
                from app.repositories.search_repository import search_anime
                res = await search_anime(m["name"])
                if res: return {"answer": await format_content_profile(res[0], "anime")}
            elif m_type == "movie":
                from app.db.mongo import get_db
                db = get_db()
                doc = await db["movies"].find_one({"_id": m["id"]})
                if doc: return {"answer": await format_content_profile(doc, "movie")}
            elif m_type == "tv_series":
                from app.repositories.search_repository import search_tv_series
                res = await search_tv_series(m["name"])
                if res: return {"answer": await format_content_profile(res[0], "tv_series")}
            
            return {"answer": f"I couldn't find media details for {m['name']}."}

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

        seen_targets = set()
        unique_enriched = []
        for r in enriched:
            if r["target"] and r["target"]["_id"] not in seen_targets:
                seen_targets.add(r["target"]["_id"])
                unique_enriched.append(r)

        # Pair each name with the specific relationship word used
        # (sensei vs teacher vs mentor), so the answer is precise
        # even when multiple words were searched.
        labeled = [
            f"{r['target']['name']} ({r['relationship']})"
            if len(relationship_names) > 1 else r["target"]["name"]
            for r in unique_enriched
        ]

        return {
            "answer":
            f"{character['name']}'s {intent} is {', '.join(labeled)}."
        }

    if intent == "family":

        details = await build_character_context(character) or {}

        family_names = [
            member["target"]["name"].strip()
            for member in details.get("family", [])
            if member.get("target") and member["target"].get("name", "").strip()
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
            member["target"]["name"].strip()
            for member in details.get("team", [])
            if member.get("target") and member["target"].get("name", "").strip()
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

    from app.services.character_profile_formatter import format_character_profile
    details = await build_character_context(character) or {}
    profile_text = format_character_profile(character, details)
    return {"answer": profile_text}