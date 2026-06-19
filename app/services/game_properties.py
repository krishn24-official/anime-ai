"""
Universal game property definitions for the Akinator-style character guessing game.

Each property is a boolean derived from character description/data.
Properties are grouped by category for clarity.

When adding new anime, add new properties in the relevant group
or create a new group — the extractor prompt auto-includes all of them.
"""

GAME_PROPERTIES = {

    # ── Gender ────────────────────────────────────────────────────────
    "isMale":           "The character is male",
    "isFemale":         "The character is female or identifies as female",

    # ── Species / Type ────────────────────────────────────────────────
    "isHuman":          "The character is human (or was human)",
    "isTitan":          "The character is a Titan or can transform into one",
    "isTitanShifter":   "The character is a Titan Shifter (can control transformation)",
    "isDevil":          "The character is a devil or demon",
    "isFishman":        "The character is a Fishman or Merman",
    "isCyborg":         "The character is a cyborg or has cybernetic enhancements",
    "isGhost":          "The character is a ghost, skeleton, or undead",
    "isAlien":          "The character is an alien or non-human entity from another world",

    # ── Status ────────────────────────────────────────────────────────
    "isAlive":          "The character is alive at the end of their main story",
    "isDeceased":       "The character dies during the main story or is confirmed dead",
    "isVillain":        "The character is a villain or antagonist",
    "isHero":           "The character is a hero or protagonist",
    "isAntiHero":       "The character is an anti-hero (morally grey, not clearly good or evil)",

    # ── Physical traits ───────────────────────────────────────────────
    "hasBlackHair":     "The character has black or very dark hair",
    "hasBlondeHair":    "The character has blonde or light yellow hair",
    "hasRedHair":       "The character has red or orange hair",
    "hasWhiteHair":     "The character has white, silver, or grey hair",
    "hasGreenHair":     "The character has green hair",
    "hasPinkHair":      "The character has pink hair",
    "hasBluHair":       "The character has blue hair",
    "hasNoHair":        "The character is bald or has no hair",
    "isTall":           "The character is notably tall",
    "isShort":          "The character is notably short or small",
    "wearsGlasses":     "The character wears glasses or goggles",

    # ── Role / Position ───────────────────────────────────────────────
    "isLeader":         "The character leads a group, squad, or organization",
    "isCaptain":        "The character holds the title of captain",
    "isCommander":      "The character is a commander or general",
    "isKing":           "The character is a king, queen, or royalty",
    "isRoyalBlood":     "The character has royal blood or royal lineage",
    "isSensei":         "The character is a teacher, mentor, or sensei",
    "isDoctor":         "The character is a doctor or medical professional",
    "isScientist":      "The character is a scientist, researcher, or inventor",
    "isSpy":            "The character works as a spy or secret agent",
    "isAssassin":       "The character is an assassin or trained killer",
    "isNavigator":      "The character is a navigator",
    "isArchaeologist":  "The character is an archaeologist or historian",
    "isCook":           "The character is a cook or chef",
    "isMusician":       "The character is a musician",

    # ── Combat ────────────────────────────────────────────────────────
    "usesSword":        "The character primarily uses a sword or blade",
    "usesMagic":        "The character uses magic or supernatural powers",
    "usesCursedEnergy": "The character uses cursed energy or cursed techniques",
    "usesBreathing":    "The character uses a breathing technique (Demon Slayer)",
    "usesGun":          "The character primarily uses firearms",
    "hasDevilFruit":    "The character has eaten a Devil Fruit",
    "hasSharingan":     "The character has or has had Sharingan",
    "hasRinnegan":      "The character has or has had Rinnegan",
    "hasNineTails":     "The character is or has been a jinchuriki of the Nine-Tails",
    "usesAkhira":       "The character uses Akhira or shadow abilities (Solo Leveling)",

    # ── Affiliations ──────────────────────────────────────────────────
    # AOT
    "isSurveyCorps":    "The character is or was a member of the Survey Corps",
    "isMilitaryPolice": "The character is or was in the Military Police Brigade",
    "isGarrison":       "The character is or was in the Garrison Regiment",
    "isFromMarley":     "The character is from or was born in Marley",
    "isAckerman":       "The character is a member of the Ackerman clan",

    # One Piece
    "isStrawHat":       "The character is a member of the Straw Hat Pirates",
    "isPirate":         "The character is a pirate",
    "isMarine":         "The character is or was a Marine",
    "isMarineAdmiral":  "The character is or was a Marine Admiral",
    "isRevolutionary":  "The character is a member of the Revolutionary Army",
    "isWarlord":        "The character is or was a Warlord of the Sea",
    "isYonko":          "The character is or was a Yonko (Emperor of the Sea)",

    # Naruto
    "isKonoha":         "The character is from or affiliated with Konohagakure (Leaf Village)",
    "isAkatsuki":       "The character is or was a member of Akatsuki",
    "isNinja":          "The character is a ninja or shinobi",
    "isSage":           "The character is a sage or uses sage mode",
    "isKage":           "The character is or was a Kage (village leader)",
    "isUchiha":         "The character is a member of the Uchiha clan",

    # Jujutsu Kaisen
    "isJujutsuSorcerer": "The character is a jujutsu sorcerer",
    "isCursedSpirit":    "The character is a cursed spirit",
    "isTokyoSchool":     "The character attends or attended Tokyo Jujutsu High",

    # Demon Slayer
    "isDemonSlayer":    "The character is a Demon Slayer Corps member",
    "isDemon":          "The character is a demon",
    "isHashira":        "The character is or was a Hashira (Pillar)",
    "isMuzan":          "The character is Muzan Kibutsuji or one of the Twelve Kizuki",

    # Dragon Ball
    "isSaiyan":         "The character is a Saiyan or half-Saiyan",
    "isZFighter":       "The character is a Z Fighter",
    "canGoSuperSaiyan": "The character can transform into Super Saiyan",

    # Bleach
    "isSoulReaper":     "The character is a Soul Reaper (Shinigami)",
    "isHollow":         "The character is a Hollow or Arrancar",
    "isQuincy":         "The character is a Quincy",

    # Fullmetal Alchemist
    "isAlchemist":      "The character is an alchemist",
    "isHomunculus":     "The character is a Homunculus",
    "isStateMilitary":  "The character is a State Alchemist or military officer",

    # Solo Leveling
    "isHunter":         "The character is a Hunter",
    "isMonarch":        "The character is a Monarch or Shadow Soldier",

    # One Punch Man
    "isHeroAssociation": "The character is a registered Hero Association member",
    "isMonsterAssociation": "The character is a Monster Association member",

    # Chainsaw Man
    "isDevilHunter":    "The character is a Devil Hunter",
    "isPartDevil":      "The character is part devil or a devil",
}


# Questions shown to the user in the game
# Each question maps to one property key
GAME_QUESTIONS = [
    # Gender
    {"key": "isMale",           "text": "Is your character male?"},
    {"key": "isFemale",         "text": "Is your character female?"},

    # Species
    {"key": "isHuman",          "text": "Is your character human?"},
    {"key": "isTitan",          "text": "Is your character a Titan?"},
    {"key": "isTitanShifter",   "text": "Is your character a Titan Shifter?"},
    {"key": "isFishman",        "text": "Is your character a Fishman?"},
    {"key": "isCyborg",         "text": "Is your character a cyborg?"},
    {"key": "isGhost",          "text": "Is your character a ghost or undead?"},

    # Status
    {"key": "isAlive",          "text": "Is your character alive?"},
    {"key": "isVillain",        "text": "Is your character a villain or antagonist?"},
    {"key": "isHero",           "text": "Is your character the main hero or protagonist?"},
    {"key": "isAntiHero",       "text": "Is your character an anti-hero (morally grey)?"},

    # Physical
    {"key": "hasBlackHair",     "text": "Does your character have black hair?"},
    {"key": "hasBlondeHair",    "text": "Does your character have blonde hair?"},
    {"key": "hasWhiteHair",     "text": "Does your character have white or silver hair?"},
    {"key": "hasRedHair",       "text": "Does your character have red hair?"},
    {"key": "hasGreenHair",     "text": "Does your character have green hair?"},
    {"key": "isShort",          "text": "Is your character notably short?"},
    {"key": "wearsGlasses",     "text": "Does your character wear glasses or goggles?"},

    # Role
    {"key": "isLeader",         "text": "Does your character lead a group or organization?"},
    {"key": "isCaptain",        "text": "Is your character a captain?"},
    {"key": "isRoyalBlood",     "text": "Does your character have royal blood?"},
    {"key": "isDoctor",         "text": "Is your character a doctor or medic?"},
    {"key": "isScientist",      "text": "Is your character a scientist or inventor?"},
    {"key": "isSensei",         "text": "Is your character a teacher or mentor?"},
    {"key": "isAssassin",       "text": "Is your character an assassin?"},
    {"key": "isNavigator",      "text": "Is your character a navigator?"},
    {"key": "isCook",           "text": "Is your character a cook or chef?"},
    {"key": "isMusician",       "text": "Is your character a musician?"},

    # Combat
    {"key": "usesSword",        "text": "Does your character primarily use a sword?"},
    {"key": "usesMagic",        "text": "Does your character use magic or supernatural powers?"},
    {"key": "hasDevilFruit",    "text": "Has your character eaten a Devil Fruit?"},
    {"key": "hasSharingan",     "text": "Does your character have the Sharingan?"},
    {"key": "hasNineTails",     "text": "Is your character a Nine-Tails jinchuriki?"},
    {"key": "usesBreathing",    "text": "Does your character use a breathing technique?"},
    {"key": "usesCursedEnergy", "text": "Does your character use cursed energy?"},

    # AOT
    {"key": "isSurveyCorps",    "text": "Is your character in the Survey Corps?"},
    {"key": "isMilitaryPolice", "text": "Is your character in the Military Police?"},
    {"key": "isFromMarley",     "text": "Is your character from Marley?"},
    {"key": "isAckerman",       "text": "Is your character from the Ackerman clan?"},

    # One Piece
    {"key": "isStrawHat",       "text": "Is your character a Straw Hat Pirate?"},
    {"key": "isPirate",         "text": "Is your character a pirate?"},
    {"key": "isMarine",         "text": "Is your character a Marine?"},
    {"key": "isYonko",          "text": "Is your character a Yonko (Emperor of the Sea)?"},
    {"key": "isRevolutionary",  "text": "Is your character in the Revolutionary Army?"},

    # Naruto
    {"key": "isNinja",          "text": "Is your character a ninja?"},
    {"key": "isAkatsuki",       "text": "Is your character a member of Akatsuki?"},
    {"key": "isUchiha",         "text": "Is your character from the Uchiha clan?"},
    {"key": "isKage",           "text": "Is your character a Kage?"},
    {"key": "isSage",           "text": "Does your character use sage mode?"},

    # JJK
    {"key": "isJujutsuSorcerer","text": "Is your character a jujutsu sorcerer?"},
    {"key": "isCursedSpirit",   "text": "Is your character a cursed spirit?"},

    # Demon Slayer
    {"key": "isDemonSlayer",    "text": "Is your character a Demon Slayer Corps member?"},
    {"key": "isDemon",          "text": "Is your character a demon?"},
    {"key": "isHashira",        "text": "Is your character a Hashira (Pillar)?"},

    # Dragon Ball
    {"key": "isSaiyan",         "text": "Is your character a Saiyan?"},
    {"key": "canGoSuperSaiyan", "text": "Can your character go Super Saiyan?"},

    # Bleach
    {"key": "isSoulReaper",     "text": "Is your character a Soul Reaper?"},
    {"key": "isHollow",         "text": "Is your character a Hollow or Arrancar?"},
    {"key": "isQuincy",         "text": "Is your character a Quincy?"},

    # FMA
    {"key": "isAlchemist",      "text": "Is your character an alchemist?"},
    {"key": "isHomunculus",     "text": "Is your character a Homunculus?"},

    # Solo Leveling
    {"key": "isHunter",         "text": "Is your character a Hunter?"},
    {"key": "isMonarch",        "text": "Is your character a Monarch?"},

    # One Punch Man
    {"key": "isHeroAssociation","text": "Is your character a registered hero?"},

    # Chainsaw Man
    {"key": "isDevilHunter",    "text": "Is your character a Devil Hunter?"},
    {"key": "isPartDevil",      "text": "Is your character part devil or a devil?"},
]