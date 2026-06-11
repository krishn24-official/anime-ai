import asyncio
import httpx

from app.db.mongo import (
    connect_db,
    close_db,
    get_db
)

from app.backend.transformers.manga_transformer import (
    transform_manga
)

ANILIST_URL = (
    "https://graphql.anilist.co"
)

QUERY = """
query ($search: String) {

  Media(
    search: $search,
    type: MANGA
  ) {

    id

    title {
      romaji
      english
      native
    }

    description

    chapters

    volumes

    status

    genres

    bannerImage

    coverImage {
      large
    }

    startDate {
      year
      month
      day
    }

    endDate {
      year
      month
      day
    }

    staff {

      edges {

        role

        node {

          name {
            full
          }
        }
      }
    }

  }
}
"""


async def fetch_and_save(
    client: httpx.AsyncClient,
    manga_name: str
):

    db = get_db()

    manga_collection = (
        db["manga"]
    )

    print(
        f"\n📚 Fetching: {manga_name}"
    )

    response = await client.post(
        ANILIST_URL,
        json={
            "query": QUERY,
            "variables": {
                "search":
                    manga_name
            }
        },
        timeout=30.0
    )

    response.raise_for_status()

    data = response.json()

    if "errors" in data:

        print(
            f"❌ AniList Error: {manga_name}"
        )

        print(
            data["errors"]
        )

        return

    media = (
        data.get("data", {})
        .get("Media")
    )

    if not media:

        print(
            f"❌ Manga not found: {manga_name}"
        )

        return

    formatted_manga = (
        transform_manga(
            media
        )
    )

    await (
        manga_collection
        .replace_one(
            {
                "_id":
                formatted_manga["_id"]
            },
            formatted_manga,
            upsert=True
        )
    )

    print(
        f"✅ Saved: "
        f"{formatted_manga['_id']}"
    )


async def main():

    print(
        "🚀 Starting manga ingestion..."
    )

    await connect_db()

    async with (
        httpx.AsyncClient()
        as client
    ):

        await fetch_and_save(
            client,
            "Naruto"
        )

        await fetch_and_save(
            client,
            "One Piece"
        )

        await fetch_and_save(
            client,
            "Jujutsu Kaisen"
        )

        await fetch_and_save(
            client,
            "Kimetsu no Yaiba"
        )

        await fetch_and_save(
            client,
            "Chainsaw Man"
        )

        await fetch_and_save(
            client,
            "Berserk"
        )

        await fetch_and_save(
            client,
            "Shingeki no Kyojin"
        )

        await fetch_and_save(
            client,
            "Na Honjaman Level Up"
        )

        await fetch_and_save(
            client,
            "Tokyo Ghoul"
        )

        await fetch_and_save(
            client,
            "Oyasumi Punpun"
        )

        await fetch_and_save(
            client,
            "Boku no Hero Academia"
        )

        await fetch_and_save(
            client,
            "One Punch-Man"
        )

        await fetch_and_save(
            client,
            "Vagabond"
        )

        await fetch_and_save(
            client,
            "SPY×FAMILY"
        )

        await fetch_and_save(
            client,
            "Vinland Saga"
        )

        await fetch_and_save(
            client,
            "Yakusoku no Neverland"
        )

        await fetch_and_save(
            client,
            "Jeonjijeok Dokja Sijeom"
        )

        await fetch_and_save(
            client,
            "Horimiya"
        )

        await fetch_and_save(
            client,
            "Blue Lock"
        )

        await fetch_and_save(
            client,
            "BLEACH"
        )

        await fetch_and_save(
            client,
            "Dandadan"
        )

        await fetch_and_save(
            client,
            "HUNTER×HUNTER"
        )

        await fetch_and_save(
            client,
            "Black Clover"
        )

        await fetch_and_save(
            client,
            "MONSTER"
        )

        await fetch_and_save(
            client,
            "20 Seiki Shounen"
        )

        await fetch_and_save(
            client,
            "Kaijuu 8-gou"
        )

        await fetch_and_save(
            client,
            "Haikyuu!!"
        )

        await fetch_and_save(
            client,
            "DEATH NOTE"
        )

        await fetch_and_save(
            client,
            "Sono Bisque Doll wa Koi wo Suru"
        )

        await fetch_and_save(
            client,
            "Dr. STONE"
        )

        # await fetch_and_save(client, "Dorohedoro")
        # await fetch_and_save(client, "SAKAMOTO DAYS")
        # await fetch_and_save(client, "Uzumaki")
        # await fetch_and_save(client, "Sousou no Frieren")
        # await fetch_and_save(client, "Houseki no Kuni")
        # await fetch_and_save(client, "Tongari Boushi no Atelier")
        # await fetch_and_save(client, "Blue Period")
        # await fetch_and_save(client, "Kaoru Hana wa Rin to Saku")
        # await fetch_and_save(client, "Kingdom")
        # await fetch_and_save(client, "SLAM DUNK")

    await close_db()


if __name__ == "__main__":

    asyncio.run(
        main()
    )
