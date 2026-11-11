"""Person/character name variants. Pure Python, no I/O.

Japanese names are written family-name first ("Gojo Satoru", "Roronoa Zoro") but
AniList stores them given-name first ("Satoru Gojo"), and middle initials vary
("Monkey D. Luffy" is stored as "Luffy Monkey").
"""

import re


def name_variants(name: str) -> list[str]:
    """The name as given, reversed, and both without initials; distinct, in that order."""
    words = name.split()
    plain = [w for w in words if not re.fullmatch(r"[A-Za-z]\.?", w)]  # drop "D." / "D"
    variants = [words, words[::-1], plain, plain[::-1]]
    return list(dict.fromkeys(" ".join(v) for v in variants if v))
