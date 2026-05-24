import asyncio
import requests

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
query ($anime: String) {

  Media(search: $anime, type: ANIME) {

    id

    title {
      english
      romaji
    }

    characters(sort: ROLE, perPage: 25) {

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


async def fetch_and_save(anime_name):

    await connect_db()

    db = get_db()

    character_collection = db["characters"]

    variables = {
        "anime": anime_name
    }

    response = requests.post(
        ANILIST_URL,
        json={
            "query": query,
            "variables": variables
        }
    )

    data = response.json()

    media = data["data"]["Media"]

    title = (
        media["title"]["english"]
        or media["title"]["romaji"]
    )

    anime_slug = create_slug(title)

    anime_db_id = f"anime_{anime_slug}"

    characters = media["characters"]["edges"]

    for character_edge in characters:

        role = character_edge.get("role")

        character = character_edge.get("node")

        if not character:
            continue

        formatted_character = transform_character(
            character,
            anime_db_id,
            role
        )

        await character_collection.replace_one(
            {"_id": formatted_character["_id"]},
            formatted_character,
            upsert=True
        )

        print(
            f"✅ Saved: {formatted_character['name']}"
        )

    await close_db()


asyncio.run(fetch_and_save("Naruto"))