import asyncio
import httpx

from app.db.mongo import (
    connect_db,
    close_db,
    get_db
)

from app.backend.transformers.character_transformer import (
    transform_character
)

from app.backend.utils.slug import create_slug


ANILIST_URL = "https://graphql.anilist.co"


query = """
query ($anime: String, $page: Int) {

  Media(search: $anime, type: ANIME) {

    title {
      english
      romaji
    }

    characters(sort: ROLE, page: $page, perPage: 25) {

      pageInfo {
        hasNextPage
        currentPage
      }

      edges {

        role

        node {

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
        }
      }
    }
  }
}
"""


async def fetch_and_save(client: httpx.AsyncClient, anime_name: str):

    db = get_db()

    character_collection = db["characters"]

    page = 1

    total_saved = 0

    while True:

        print(f"\n📄 Fetching page {page} for {anime_name}...")

        variables = {
            "anime": anime_name,
            "page": page
        }

        response = await client.post(
            ANILIST_URL,
            json={
                "query": query,
                "variables": variables
            },
            timeout=30.0
        )

        response.raise_for_status()
        data = response.json()

        # ERROR HANDLING
        if "errors" in data:
            print("❌ GraphQL Errors:")
            print(data["errors"])
            break

        media = data.get("data", {}).get("Media")

        if not media:
            print("❌ No media found")
            break

        title = (
            media["title"].get("english")
            or media["title"].get("romaji")
        )

        anime_slug = create_slug(title)

        anime_db_id = f"anime_{anime_slug}"

        characters_data = media["characters"]

        characters = characters_data["edges"]

        for character_edge in characters:

            role = character_edge.get("role")

            character = character_edge.get("node")

            if not character:
                continue

            if not character.get("name", {}).get("full"):
                continue

            formatted_character = transform_character(
                character,
                anime_db_id,
                role
            )

            # CHECK EXISTING CHARACTER
            existing_character = await character_collection.find_one(
                {"_id": formatted_character["_id"]}
            )

            if existing_character:

                # MERGE ANIME IDS
                existing_anime_ids = existing_character.get(
                    "anime_ids",
                    []
                )

                merged_anime_ids = list(
                    set(
                        existing_anime_ids +
                        formatted_character["anime_ids"]
                    )
                )

                formatted_character["anime_ids"] = merged_anime_ids

            await character_collection.replace_one(
                {"_id": formatted_character["_id"]},
                formatted_character,
                upsert=True
            )

            total_saved += 1

            print(
                f"✅ Saved: {formatted_character['name']}"
            )

        has_next_page = (
            characters_data["pageInfo"]["hasNextPage"]
        )

        if not has_next_page:
            break

        page += 1

    print(
        f"\n🎉 Total characters saved for {anime_name}: {total_saved}"
    )


async def main():

    print("🚀 Starting character ingestion...")

    await connect_db()

    async with httpx.AsyncClient() as client:
        await fetch_and_save(client, "Naruto")

        await fetch_and_save(client, "Naruto: Shippuden")

        await fetch_and_save(client, "Boruto: Naruto Next Generations")

        await fetch_and_save(client, "BORUTO: NARUTO THE MOVIE")

        # await fetch_and_save(client, "DEATH NOTE")

        # await fetch_and_save(client, "ONE PIECE")

        # await fetch_and_save(client, "Shingeki no Kyojin: The Final Season")

        # await fetch_and_save(client, "Shingeki no Kyojin Season 3")

        # await fetch_and_save(client, "Shingeki no Kyojin Season 2")

        # await fetch_and_save(client, "Shingeki no Kyojin")

        # await fetch_and_save(client, "Jujutsu Kaisen: Kaigyoku・Gyokusetsu")
        # await fetch_and_save(client, "Jujutsu Kaisen 2nd Season")
        # await fetch_and_save(client, "Jujutsu Kaisen: Shimetsu Kaiyuu - Zenpen")
        # await fetch_and_save(client, "Jujutsu Kaisen 0")
        # await fetch_and_save(client, "Jujutsu Kaisen")

    await close_db()


asyncio.run(main())