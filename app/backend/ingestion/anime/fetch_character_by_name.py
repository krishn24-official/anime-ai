import asyncio
import httpx

from app.db.mongo import (
    connect_db,
    close_db,
    get_db
)

from app.backend.ingestion.anime.anilist_resolvers import (
    resolve_or_create_voice_actor,
    resolve_or_create_character,
)
from app.services.game_property_extractor import extract_game_properties


ANILIST_URL = "https://graphql.anilist.co"


QUERY = """
query ($id: Int, $name: String) {
  Character(id: $id, search: $name) {
    id
    name {
      full
      native
    }
    image {
      large
    }
    gender
    description
    age
    dateOfBirth {
      day
      month
    }
    media(sort: POPULARITY_DESC, perPage: 5) {
      edges {
        node {
          id
          title {
            english
            romaji
          }
          type
        }
        characterRole
      }
    }
    voiceActors(language: JAPANESE, sort: [LANGUAGE]) {
      id
      name {
        full
        native
      }
      image {
        large
      }
      dateOfBirth {
        year
        month
        day
      }
      gender
      description
    }
  }
}
"""


async def fetch_and_save(
    client: httpx.AsyncClient,
    character_name: str | int,
    expected_name: str | None = None,
):
    """
    Fetch a character by name or ID from AniList and save to DB.

    character_name  -- the search term or ID sent to AniList
    expected_name   -- optional: if AniList returns a different name,
                       warn but still save (don't silently save wrong character).
                       Set to False to skip the check entirely.
    """

    print(f"\n Fetching: {character_name}")

    variables = {}
    if isinstance(character_name, int) or (isinstance(character_name, str) and character_name.isdigit()):
        variables["id"] = int(character_name)
    else:
        variables["name"] = character_name

    response = await client.post(
        ANILIST_URL,
        json={
            "query": QUERY,
            "variables": variables
        },
        timeout=30.0
    )

    response.raise_for_status()
    data = response.json()

    if "errors" in data:
        print(f"❌ AniList Error for '{character_name}': {data['errors']}")
        return

    character = data.get("data", {}).get("Character")

    if not character:
        print(f"❌ Character not found: {character_name}")
        return

    returned_name = character.get("name", {}).get("full", "")

    if not returned_name:
        print(f"❌ Character has no name: {character_name}")
        return

    # Name mismatch check
    if expected_name is not None:
        check_name = expected_name
    elif not isinstance(character_name, int) and not (isinstance(character_name, str) and character_name.isdigit()):
        check_name = character_name
    else:
        check_name = False

    if (
        check_name is not False
        and returned_name.lower() != check_name.lower()
    ):
        print(
            f"  ⚠️  Name mismatch: searched '{character_name}' "
            f"→ got '{returned_name}' (expected '{check_name}'). Saving anyway."
        )

    # Build anime_ids from all media this character appears in
    anime_ids = []
    role = "SUPPORTING"

    media_edges = character.get("media", {}).get("edges", [])

    for edge in media_edges:
        node = edge.get("node", {})
        media_type = node.get("type")
        edge_role = edge.get("characterRole", "SUPPORTING")

        if media_type == "ANIME":
            title = (
                node.get("title", {}).get("english")
                or node.get("title", {}).get("romaji")
                or ""
            )
            if title:
                from app.backend.utils.slug import create_slug
                anime_slug = create_slug(title)
                anime_ids.append(f"anime_{anime_slug}")

                # Use the highest role (MAIN > SUPPORTING > BACKGROUND)
                if edge_role == "MAIN":
                    role = "MAIN"
                elif edge_role == "SUPPORTING" and role != "MAIN":
                    role = "SUPPORTING"

    # Use first anime_id as primary, or empty string if none
    primary_anime_id = anime_ids[0] if anime_ids else ""


    # ── Resolve voice actors (id-based dedup via shared resolver) ──
    voice_actor_ids = []
    voice_actors_data = character.get("voiceActors", [])
    for va_data in voice_actors_data:
        if not va_data.get("name", {}).get("full"):
            continue
        va_id = await resolve_or_create_voice_actor(va_data)
        if va_id:
            voice_actor_ids.append(va_id)
            print(f"   Voice Actor: {va_data['name']['full']}")

    # ── Resolve character (anilist_id-based dedup via shared resolver) ──
    # Primary lookup: source_metadata.anilist_id — prevents name collisions.
    # This is the fix that prevents the Kohaku-style collision bug.
    # Derive the primary anime_id for transform_character (the first one from the media list).
    char_id = await resolve_or_create_character(
        char_node=character,
        anime_id=primary_anime_id,
        role=role,
        voice_actor_ids=voice_actor_ids,
    )

    # If the character had additional anime_ids from its media edges beyond the primary,
    # merge them in now (resolve_or_create_character only seeds with primary_anime_id).
    if char_id and len(anime_ids) > 1:
        db = get_db()
        existing = await db["characters"].find_one({"_id": char_id})
        if existing:
            merged = list(set(existing.get("anime_ids", []) + anime_ids))
            await db["characters"].update_one(
                {"_id": char_id},
                {"$set": {"anime_ids": merged}}
            )

    if not char_id:
        print(f"  ❌ Failed to save character: {returned_name}")
        return

    print(f"  ✅ Saved: {char_id}")

    # Auto-extract game properties if character is new and has a description
    db = get_db()
    doc = await db["characters"].find_one({"_id": char_id})
    if doc and doc.get("description") and not doc.get("game_properties"):
        print(f"  🎮 Extracting game properties...")
        game_properties = await extract_game_properties(
            character_name=doc["name"],
            description=doc["description"],
            gender=doc.get("gender"),
            anime_ids=doc.get("anime_ids", []),
        )
        if game_properties:
            await db["characters"].update_one(
                {"_id": char_id},
                {"$set": {"game_properties": game_properties}}
            )
            print(f"  🎮 Properties: {game_properties}")


async def main():

    print("🚀 Starting individual character ingestion...")

    await connect_db()

    async with httpx.AsyncClient() as client:

        # Characters list.
        # Format options:
        #   "Name"                    → search + warn if name doesn't match
        #   ("Search term", "Expected name")  → search by term, verify against expected
        #   ("Search term", False)    → search + skip name check (trust AniList)
        #
        # Examples:
        #   "Monkey D. Dragon"        → AniList may return "Dragon", will warn
        #   ("Dragon", "Monkey D. Dragon")  → search "Dragon", save as-is (AniList name wins)
        #   ("Dragon", False)         → search "Dragon", no check

        characters = [

            # Naruto
            # "Sumire Kakei",
            # "Wasabi Izuno",
            # "Yahiko",
            # "Portgas D. Rouge",
            # "Sabo no Chichi",
            # "Sabo no Haha",
            # "Olvia Nico",
            # "Cobra Nefertari",
            # "Naruto Uzumaki",
            # "Sasuke Uchiha",
            # "Sakura Haruno",
            # "Kakashi Hatake",
            # "Itachi Uchiha",
            # "Hinata Hyuga",
            # "Gaara",
            # "Rock Lee",
            # "Neji Hyuga",
            # "Shikamaru Nara",
            # "Minato Namikaze",
            # "Tsunade",
            # "Jiraiya",
            # "Orochimaru",
            # "Pain",
            # "Konan",
            # "Obito Uchiha",
            # "Madara Uchiha",
            # "Kaguya Otsutsuki",
            # "Might Guy",

            # # One Piece — D. family members use alias pattern
            # "Monkey D. Luffy",
            # (4884, False),                  # Monkey D. Dragon (AniList has just "Dragon", ID: 4884)
            # (8064, False),                # Monkey D. Garp (AniList has just "Garp", ID: 8064)
            # "Roronoa Zoro",
            # "Nami",
            # "Usopp",
            # "Sanji",
            # "Tony Tony Chopper",
            # "Nico Robin",
            # "Franky",
            # "Brook",
            # "Jinbe",
            # ("Portgas D. Ace", False),
            # "Trafalgar Law",
            # "Boa Hancock",
            # "Shanks",
            # "Whitebeard",
            # "Blackbeard",
            # "Kaido",
            # "Big Mom",
            # "Dracule Mihawk",
            # "Sabo",

            # # Jujutsu Kaisen
            # "Yuji Itadori",
            # "Megumi Fushiguro",
            # "Nobara Kugisaki",
            # "Satoru Gojo",
            # "Ryomen Sukuna",
            # "Aoi Todo",
            # "Kento Nanami",
            # "Toge Inumaki",
            # "Panda",
            # "Yuta Okkotsu",

            # # Demon Slayer
            # "Tanjiro Kamado",
            # "Nezuko Kamado",
            # "Zenitsu Agatsuma",
            # "Inosuke Hashibira",
            # "Giyu Tomioka",
            # "Shinobu Kocho",
            # "Rengoku Kyojuro",
            # "Tengen Uzui",
            # "Muzan Kibutsuji",
            # "Akaza",

            # # Dragon Ball
            # "Goku",
            # "Vegeta",
            # "Gohan",
            # "Piccolo",
            # "Frieza",
            # "Cell",
            # "Majin Buu",
            # "Trunks",
            # "Krillin",
            # "Bulma",

            # # AOT
            # "Eren Yeager",
            # "Mikasa Ackerman",
            # "Armin Arlert",
            # "Levi Ackerman",
            # "Erwin Smith",
            # "Hange Zoe",
            # "Historia Reiss",
            # "Reiner Braun",
            # "Zeke Yeager",
            # "Annie Leonhart",

            # # Death Note
            # "Light Yagami",
            # "L Lawliet",
            # "Ryuk",
            # "Near",
            # "Mello",
            # "Misa Amane",

            # # Fullmetal Alchemist
            # "Edward Elric",
            # "Alphonse Elric",
            # "Roy Mustang",
            # "Winry Rockbell",
            # "Riza Hawkeye",
            # "Scar",
            # "Greed",
            # "Envy",
            # "Wrath",
            # "Father",

            # # Bleach
            # "Ichigo Kurosaki",
            # "Rukia Kuchiki",
            # "Orihime Inoue",
            # "Uryu Ishida",
            # "Yasutora Sado",
            # "Byakuya Kuchiki",
            # "Toshiro Hitsugaya",
            # "Sosuke Aizen",
            # "Kisuke Urahara",
            # "Yoruichi Shihoin",

            # # Solo Leveling
            # "Sung Jinwoo",
            # "Cha Hae-In",

            # # Chainsaw Man
            # "Denji",
            # "Power",
            # "Makima",
            # "Aki Hayakawa",
            # "Pochita",

            # # One Punch Man
            # "Saitama",
            # "Genos",
            # ("Speed-o'-Sound Sonic", False),
            # "Boros",
            # "Bang",

            # # Frieren
            # "Frieren",
            # "Fern",
            # "Stark",
            # "Himmel",
            # "Heiter",

            # # Dr. Stone
            # "Senku Ishigami",
            # "Taiju Oki",
            # "Chrome",
            # "Kohaku",
            # "Gen Asagiri",
        ]

        for entry in characters:
            # Support both plain string and (search_term, expected_name) tuple
            if isinstance(entry, tuple):
                name, expected = entry
            else:
                name, expected = entry, None

            try:
                await fetch_and_save(client, name, expected_name=expected)
                await asyncio.sleep(0.7)
            except Exception as e:
                print(f"❌ Error fetching '{name}': {e}")

    await close_db()
    print("\n🏁 Done.")


if __name__ == "__main__":
    asyncio.run(main())