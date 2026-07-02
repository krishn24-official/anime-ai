# =========================
# ANIME STATUS
# =========================

STATUS_MAPPING = {
    "FINISHED": "completed",
    "RELEASING": "ongoing",
    "NOT_YET_RELEASED": "upcoming",
    "CANCELLED": "cancelled",
    "HIATUS": "hiatus"
}


# =========================
# ANIME TYPE
# =========================

TYPE_MAPPING = {
    "TV": "tv",
    "TV_SHORT": "tv_short",
    "MOVIE": "movie",
    "SPECIAL": "special",
    "OVA": "ova",
    "ONA": "ona",
    "MUSIC": "music"
}


# =========================
# SOURCE MATERIAL
# =========================

SOURCE_MAPPING = {
    "ORIGINAL": "original",
    "MANGA": "manga",
    "LIGHT_NOVEL": "light_novel",
    "VISUAL_NOVEL": "visual_novel",
    "VIDEO_GAME": "game",
    "WEB_NOVEL": "web_novel",
    "NOVEL": "novel",
    "DOUJINSHI": "doujinshi",
    "COMIC": "comic",
    "LIVE_ACTION": "live_action",
    "MULTIMEDIA_PROJECT": "multimedia_project",
    "OTHER": "other"
}


# =========================
# RELATIONSHIP TYPES
# Broad Categories
# =========================

RELATIONSHIP_TYPES = [
    "family",
    "romance",
    "friendship",
    "academy",
    "team",
    "mentor",
    "combat",
    "organization",
    "political",
    "other"
]

EVENT_TYPES = [

    "anime_release",

    "anime_milestone",

    "manga_release",

    "manga_milestone",

    "movie_release",

    "character_debut",

    "special"
]

ENTITY_CATEGORIES = [
    # Geographic
    "village",
    "city",
    "town",
    "country",
    "kingdom",
    "island",
    "continent",
    "realm",
    "dimension",

    # Organizations
    "organization",
    "military",
    "government",
    "academy",
    "guild",
    "pirate_crew",
    "crime_organization",
    "mercenary_group",
    "religious_group",

    # Family / Social
    "clan",
    "family",
    "tribe",
    "house",

    # Military Divisions
    "division",
    "squad",
    "corps",
    "unit",

    # Species / Race
    "species",
    "species_group",
    "race",

    # Schools
    "school",
    "college",

    # Misc
    "other"
]

ENTITY_RELATIONSHIPS = [

    "parent",

    "subdivision",

    "branch",

    "allied_with",

    "enemy_of",

    "merged_into",

    "successor_of",

    "predecessor_of",

    "located_in",

    "governs",

    "protected_by",

    "controlled_by"
]


# =========================
# RELATIONSHIPS
# Specific Edge Meanings
# =========================

RELATIONSHIPS = {

    # =====================
    # FAMILY
    # =====================

    "family": [
        "father",
        "mother",
        "son",
        "daughter",
        "brother",
        "sister",
        "husband",
        "wife",
        "cousin",
        "uncle",
        "aunt",
        "grandfather",
        "grandmother",
        "grandson",
        "granddaughter",
        "father_in_law",
        "mother_in_law",
        "son_in_law",
        "daughter_in_law",
        "brother_in_law",
        "sister_in_law",
        "niece",
    ],


    # =====================
    # ROMANCE
    # =====================

    "romance": [
        "crush",
        "love_interest",
        "fiance",
        "partner",
        "ex_partner"
    ],


    # =====================
    # FRIENDSHIP
    # =====================

    "friendship": [
        "friend",
        "best_friend",
        "childhood_friend",
        "ally"
    ],


    # =====================
    # ACADEMY
    # =====================

    "academy": [
        "classmate",
        "senior",
        "junior"
    ],


    # =====================
    # TEAM
    # =====================

    "team": [
        "teammate",
        "leader",
        "captain",
        "member"
    ],


    # =====================
    # MENTOR
    # =====================

    "mentor": [
        "student",
        "sensei",
        "mentor",
        "teacher",
    ],


    # =====================
    # COMBAT
    # =====================

    "combat": [
        "rival",
        "enemy",
        "killer",
        "target",
        "assassin"
    ],


    # =====================
    # ORGANIZATION
    # =====================

    "organization": [

        # Membership
        "member",
        "former_member",

        # Leadership
        "leader",
        "former_leader",
        "captain",
        "vice_captain",
        "commander",
        "chief",
        "chairman",
        "elder",

        # Administrative
        "founder",
        "co_founder",
        "successor",
        "advisor",
        "representative",

        # Educational
        "teacher",
        "student",
        "principal",
        "instructor",

        # Military
        "soldier",
        "officer",
        "general",

        # Special
        "guardian",
        "bodyguard",
        "ambassador"
    ],


    # =====================
    # POLITICAL
    # =====================

    "political": [
        "kage",
        "advisor",
        "bodyguard"
    ]
}