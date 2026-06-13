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

    print("🚀 Starting anime ingestion...")

    await connect_db()

    async with httpx.AsyncClient() as client:

        # Naruto
        # await fetch_and_save(client, "Naruto")
        # await fetch_and_save(client, "Naruto: Shippuden")
        # await fetch_and_save(client, "Boruto: Naruto Next Generations")
        # await fetch_and_save(client, "BORUTO: NARUTO THE MOVIE")
        # await fetch_and_save(client,"ROAD OF NARUTO")
        # await fetch_and_save(client,"NARUTO: Dai Gekitotsu! Maboroshi no Chitei Iseki Dattebayo")
        # await fetch_and_save(client,"BORUTO: NARUTO THE MOVIE - Naruto ga Hokage ni Natta Hi")
        # await fetch_and_save(client,"NARUTO: Shippuuden - Hi no Ishi wo Tsugu Mono")
        # await fetch_and_save(client,"NARUTO: Blood Prison")
        # await fetch_and_save(client,"ROAD TO NINJA: NARUTO THE MOVIE")
        # await fetch_and_save(client,"NARUTO: Shippuuden - The Lost Tower")
        # await fetch_and_save(client,"THE LAST: NARUTO THE MOVIE")
        # await fetch_and_save(client,"NARUTO: Takigakure no Shitou - Ore ga Eiyuu Dattebayo!")
        # await fetch_and_save(client,"NARUTO: Shippuuden - Kizuna")
        # await fetch_and_save(client,"NARUTO: Honoo no Chuunin Shiken! Naruto vs Konohamaru!!")
        # await fetch_and_save(client,"NARUTO: THE CROSS ROADS")
        # await fetch_and_save(client,"NARUTO: Akaki Yotsuba no Clover wo Sagase")
        # await fetch_and_save(client,"NARUTO: Shippuuden - Sunny Side Battle!!!")
        # await fetch_and_save(client,"NARUTO: Shippuuden - Shippu! 'Konoha Gakuen Den")

        # One Piece
        await fetch_and_save(client, "ONE PIECE")
        await fetch_and_save(client, "ONE PIECE STAMPEDE")
        await fetch_and_save(client, "ONE PIECE: ROMANCE DAWN STORY")
        await fetch_and_save(client, "ONE PIECE HEROINES")
        await fetch_and_save(client, "ONE PIECE: Heart of Gold")
        await fetch_and_save(client, "ONE PIECE FILM: Z")
        await fetch_and_save(client, "ONE PIECE FILM: RED")
        await fetch_and_save(client, "ONE PIECE THE MOVIE: Omatsuri Danshaku to Himitsu no Shima")
        await fetch_and_save(client, "ONE PIECE FILM: STRONG WORLD")
        await fetch_and_save(client, "ONE PIECE FILM: GOLD")
        await fetch_and_save(client, "ONE PIECE THE MOVIE: Karakuri-jou no Mecha Kyohei")
        await fetch_and_save(client, "ONE PIECE FAN LETTER")

        # JJK
        # await fetch_and_save(client, "Jujutsu Kaisen")
        # await fetch_and_save(client, "Jujutsu Kaisen 2nd Season")
        # await fetch_and_save(client, "Jujutsu Kaisen 0")

        # Demon Slayer
        # await fetch_and_save(client, "Kimetsu no Yaiba")
        # await fetch_and_save(client, "Kimetsu no Yaiba: Yuukaku-hen")
        # await fetch_and_save(client, "Kimetsu no Yaiba: Mugen Ressha-hen")
        # await fetch_and_save(client, "Kimetsu no Yaiba: Hashira Geiko-hen")
        # await fetch_and_save(client, "Kimetsu no Yaiba: Katanakaji no Sato-hen")

        # Solo Leveling
        # await fetch_and_save(client, "Ore dake Level Up na Ken")
        # await fetch_and_save(
        #     client,
        #     "Ore dake Level Up na Ken: Season 2 - Arise from the Shadow"
        # )

        # Chainsaw Man
        # await fetch_and_save(client, "Chainsaw Man")

        # # One Punch Man
        # await fetch_and_save(client, "One Punch Man")
        # await fetch_and_save(client, "One Punch Man 2")

        # # Frieren
        # await fetch_and_save(client, "Sousou no Frieren")
        # await fetch_and_save(client, "Sousou no Frieren 2nd Season")

        # # Dragon Ball
        # await fetch_and_save(client, "Dragon Ball")
        # await fetch_and_save(client, "Dragon Ball Z")
        # await fetch_and_save(client, "Dragon Ball Super")
        # await fetch_and_save(client, "Dragon Ball GT")
        # await fetch_and_save(client, "Dragon Ball Kai")
        # await fetch_and_save(client, "Dragon Ball DAIMA")

        # # Death Note
        # await fetch_and_save(client, "DEATH NOTE")

        # # Dr Stone
        # await fetch_and_save(client, "Dr. STONE")
        # await fetch_and_save(client, "Dr. STONE: STONE WARS")
        # await fetch_and_save(client, "Dr. STONE: Ryuusui")
        # await fetch_and_save(client, "Dr. STONE: NEW WORLD")
        # await fetch_and_save(client, "Dr. STONE: NEW WORLD Part 2")
        # await fetch_and_save(client, "Dr. STONE: SCIENCE FUTURE")
        # await fetch_and_save(client, "Dr. STONE: SCIENCE FUTURE Part 2")
        # await fetch_and_save(client, "Dr. STONE: SCIENCE FUTURE Part 3")

        # # AOT
        # await fetch_and_save(client, "Shingeki no Kyojin")
        # await fetch_and_save(client, "Shingeki no Kyojin Season 2")
        # await fetch_and_save(client, "Shingeki no Kyojin Season 3")
        # await fetch_and_save(client, "Shingeki no Kyojin: The Final Season")

        # # Bleach
        # await fetch_and_save(client, "Bleach")
        # await fetch_and_save(client, "BLEACH: Sennen Kessen-hen")

        # # FMAB
        # await fetch_and_save(client, "Fullmetal Alchemist: Brotherhood")

        # # Movies
        # await fetch_and_save(client, "Shigatsu wa Kimi no Uso")
        # await fetch_and_save(client, "Kimi no Na wa.")
        # await fetch_and_save(client, "Tenki no Ko")

    await close_db()


if __name__ == "__main__":
    asyncio.run(main())