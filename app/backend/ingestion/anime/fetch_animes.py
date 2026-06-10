import asyncio
import httpx

from app.db.mongo import (
    connect_db,
    close_db,
    get_db
)

from app.backend.transformers.anime_transformer import (
    transform_anime
)


ANILIST_URL = "https://graphql.anilist.co"


ANIME_LIST = [

    "Naruto",
    "Naruto: Shippuden",
    "Boruto: Naruto Next Generations",
    "BORUTO: NARUTO THE MOVIE",

    "ONE PIECE",

    "Jujutsu Kaisen",
    "Jujutsu Kaisen 2nd Season",
    "Jujutsu Kaisen 0",

    "Kimetsu no Yaiba",
    "Kimetsu no Yaiba: Yuukaku-hen",
    "Kimetsu no Yaiba: Mugen Ressha-hen",
    "Kimetsu no Yaiba: Hashira Geiko-hen",
    "Kimetsu no Yaiba: Katanakaji no Sato-hen",

    "Ore dake Level Up na Ken",
    "Ore dake Level Up na Ken: Season 2 - Arise from the Shadow",

    "Chainsaw Man",

    "One Punch Man",
    "One Punch Man 2",

    "Sousou no Frieren",
    "Sousou no Frieren 2nd Season",

    "Dragon Ball",
    "Dragon Ball Z",
    "Dragon Ball Super",
    "Dragon Ball GT",
    "Dragon Ball Kai",
    "Dragon Ball DAIMA",

    "DEATH NOTE",

    "Dr. STONE",
    "Dr. STONE: STONE WARS",
    "Dr. STONE: Ryuusui",
    "Dr. STONE: NEW WORLD",
    "Dr. STONE: NEW WORLD Part 2",
    "Dr. STONE: SCIENCE FUTURE",
    "Dr. STONE: SCIENCE FUTURE Part 2",
    "Dr. STONE: SCIENCE FUTURE Part 3",

    "Shingeki no Kyojin",
    "Shingeki no Kyojin Season 2",
    "Shingeki no Kyojin Season 3",
    "Shingeki no Kyojin: The Final Season",

    "Bleach",
    "BLEACH: Sennen Kessen-hen",

    "Fullmetal Alchemist: Brotherhood",

    "Shigatsu wa Kimi no Uso",
    "Kimi no Na wa.",
    "Tenki no Ko"
]


QUERY = """
query ($anime: String) {

  Media(
    search: $anime,
    type: ANIME
  ) {

    id

    title {
      english
      romaji
      native
    }

    synonyms

    format

    status

    genres

    season

    seasonYear

    source

    episodes

    duration

    averageScore

    coverImage {
      large
    }

    bannerImage

    studios {
      nodes {
        name
      }
    }
  }
}
"""


async def fetch_and_save(client: httpx.AsyncClient, anime_name: str):

    db = get_db()

    anime_collection = db["anime"]

    print(f"\n🎬 Fetching: {anime_name}")

    response = await client.post(
        ANILIST_URL,
        json={
            "query": QUERY,
            "variables": {
                "anime": anime_name
            }
        },
        timeout=30.0
    )

    response.raise_for_status()
    data = response.json()

    if "errors" in data:

        print(
            f"❌ AniList Error: {anime_name}"
        )

        print(data["errors"])

        return

    media = (
        data
        .get("data", {})
        .get("Media")
    )

    if not media:

        print(
            f"❌ Anime not found: {anime_name}"
        )

        return

    formatted_anime = transform_anime(
        media
    )

    await anime_collection.replace_one(
        {"_id": formatted_anime["_id"]},
        formatted_anime,
        upsert=True
    )

    print(
        f"✅ Saved: {formatted_anime['_id']}"
    )


async def main():

    await connect_db()

    async with httpx.AsyncClient() as client:
        for anime_name in ANIME_LIST:

            try:

                await fetch_and_save(
                    client,
                    anime_name
                )

                await asyncio.sleep(1)

            except Exception as e:

                print(
                    f"❌ Failed: {anime_name}"
                )

                print(e)

    await close_db()


print(
    "🚀 Starting anime ingestion..."
)

asyncio.run(main())