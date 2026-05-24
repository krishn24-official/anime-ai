import asyncio
import requests

from app.db.mongo import (
    connect_db,
    close_db,
    get_anime_collection
)

from app.backend.transformers.anime_transformer import transform_anime

ANILIST_URL = "https://graphql.anilist.co"

query = """
query ($search: String) {
  Media(search: $search, type: ANIME) {

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

    studios(isMain: true) {
      nodes {
        name
      }
    }
  }
}
"""


async def fetch_and_save():

    await connect_db()

    anime_collection = get_anime_collection()

    variables = {
        "search": "Naruto"
    }

    response = requests.post(
        ANILIST_URL,
        json={
            "query": query,
            "variables": variables
        }
    )

    data = response.json()

    anime_data = data["data"]["Media"]

    formatted_anime = transform_anime(anime_data)

    await anime_collection.replace_one(
        {"_id": formatted_anime["_id"]},
        formatted_anime,
        upsert=True
    )

    print("✅ Anime saved successfully!")

    await close_db()


asyncio.run(fetch_and_save())