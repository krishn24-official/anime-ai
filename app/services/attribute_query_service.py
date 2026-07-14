import re
from typing import Optional, Tuple

ATTRIBUTE_MAP = {
    # Media Attributes
    "director": "director",
    "directors": "director",
    "writer": "writers",
    "writers": "writers",
    "author": "writers",
    "cast": "cast",
    "actor": "cast",
    "actors": "cast",
    
    # Character Attributes
    "hair color": "hair_color",
    "hair": "hair_color",
    "height": "height",
    "birthday": "birthday",
    "birth day": "birthday",
    "birthdate": "birthday",
    "birth date": "birthday",
    "age": "age",
    "affiliation": "affiliations",
    "affiliations": "affiliations",
    "ability": "abilities",
    "abilities": "abilities",
    "power": "abilities",
    "powers": "abilities",
    
    # Common
    "description": "description",
    "plot": "description",
    "story": "description",
}

def detect_attribute_intent(msg: str) -> Optional[Tuple[str, str, Optional[str]]]:
    """
    Returns (entity_name, attribute_key, explicit_type) or None.
    """
    msg_lower = msg.lower().strip("? ")
    
    # Strip common question prefixes
    msg_lower = re.sub(r"^(who is|who's|whos|what is|whats|tell me about|show me|get|what are)\s+(the\s+)?", "", msg_lower)
    
    found_attr = None
    found_key = None
    remaining = None
    
    # Sort phrases by length descending to match longest first (e.g., "hair color" before "hair")
    sorted_phrases = sorted(ATTRIBUTE_MAP.keys(), key=len, reverse=True)
    
    for phrase in sorted_phrases:
        key = ATTRIBUTE_MAP[phrase]
        
        # Pattern 1: "<phrase> of <entity>"
        match = re.search(rf"^{phrase}\s+of\s+(.+)$", msg_lower)
        if match:
            found_attr = phrase
            found_key = key
            remaining = match.group(1).strip()
            break
            
        # Pattern 2: "<entity> <phrase>"
        match = re.search(rf"^(.+?)(?:'s)?\s+{phrase}$", msg_lower)
        if match:
            found_attr = phrase
            found_key = key
            remaining = match.group(1).strip()
            break
            
        # Pattern 3: "<phrase> for <entity>"
        match = re.search(rf"^{phrase}\s+for\s+(.+)$", msg_lower)
        if match:
            found_attr = phrase
            found_key = key
            remaining = match.group(1).strip()
            break

    if not found_key or not remaining:
        return None
        
    explicit_type = None
    entity_name = remaining
    
    if "movie" in remaining:
        explicit_type = "movie"
        entity_name = re.sub(r"\b(the |a )?movies?\b", "", remaining).strip()
    elif "anime" in remaining:
        explicit_type = "anime"
        entity_name = re.sub(r"\b(the |an )?animes?\b", "", remaining).strip()
    elif "tv show" in remaining or "tv series" in remaining or "series" in remaining:
        explicit_type = "tv_series"
        entity_name = re.sub(r"\b(the |a )?(tv shows?|tv series|series)\b", "", remaining).strip()
    elif "character" in remaining:
        explicit_type = "character"
        entity_name = re.sub(r"\b(the |a )?characters?\b", "", remaining).strip()
        
    if entity_name.endswith("'s"):
        entity_name = entity_name[:-2].strip()
    if entity_name.endswith("-"):
        entity_name = entity_name[:-1].strip()
        
    return entity_name, found_key, explicit_type
