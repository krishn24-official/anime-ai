"""
Defines how relationships pair up — used to auto-generate the inverse
document when you only specify one direction in the CSV.

SYMMETRIC relations: the inverse is the same word (A and B are teammates).
ASYMMETRIC relations: the inverse is a different word (A is B's father ->
                       B is A's son/daughter).

For asymmetric relations, the CSV lets you specify the inverse explicitly
per-row (since "son" vs "daughter" depends on the target's gender), but
falls back to this map's default if left blank.
"""

SYMMETRIC_RELATIONS = {
    "teammate", "classmate", "friend", "best_friend",
    "rival", "cousin", "sibling", "brother", "sister",
    "brother_in_law", "sister_in_law", "twin",
}

# Default inverse for common asymmetric relations.
# CSV can override with an explicit inverse_relationship column value.
DEFAULT_INVERSE = {
    "father": "child",
    "mother": "child",
    "son": "parent",
    "daughter": "parent",
    "parent": "child",
    "child": "parent",

    "grandfather": "grandchild",
    "grandmother": "grandchild",
    "grandson": "grandparent",
    "granddaughter": "grandparent",

    "uncle": "nephew_or_niece",
    "aunt": "nephew_or_niece",
    "nephew": "uncle_or_aunt",
    "niece": "uncle_or_aunt",

    "husband": "wife",
    "wife": "husband",
    "spouse": "spouse",

    "mentor": "student",
    "sensei": "student",
    "teacher": "student",
    "student": "mentor",

    "master": "apprentice",
    "apprentice": "master",

    "leader": "subordinate",
    "subordinate": "leader",

    "crush": "crush",          # often one-directional in fiction, default same
    "enemy": "enemy",
    "ally": "ally",
}


def get_inverse_relationship(relationship: str, explicit_inverse: str | None = None) -> str:
    """Returns the inverse relationship word."""
    if explicit_inverse and explicit_inverse.strip():
        return explicit_inverse.strip().lower()

    relationship = relationship.strip().lower()

    if relationship in SYMMETRIC_RELATIONS:
        return relationship

    return DEFAULT_INVERSE.get(relationship, relationship)


def is_symmetric(relationship: str) -> bool:
    return relationship.strip().lower() in SYMMETRIC_RELATIONS