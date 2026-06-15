import asyncio

import httpx

from app.db.mongo import connect_db, close_db, get_db
from app.config import OMDB_API_KEY, OMDB_BASE_URL
from app.backend.transformers.movie_transformer import transform_movie


async def fetch_and_save(client: httpx.AsyncClient, title: str):

    db = get_db()

    movies_collection = db["movies"]

    print(f"\n🎬 Fetching: {title}")

    response = await client.get(
        OMDB_BASE_URL,
        params={
            "apikey": OMDB_API_KEY,
            "t": title,
            "type": "movie",
            "plot": "full",
        },
        timeout=30.0
    )

    response.raise_for_status()
    data = response.json()

    if data.get("Response") != "True":
        print(f"❌ Movie not found: {title} ({data.get('Error')})")
        return

    formatted_movie = transform_movie(data)

    await movies_collection.replace_one(
        {"_id": formatted_movie["_id"]},
        formatted_movie,
        upsert=True
    )

    print(f"✅ Saved: {formatted_movie['_id']}")


async def main():

    if not OMDB_API_KEY:
        print("❌ OMDB_API_KEY not set in .env")
        return

    print("🚀 Starting movie ingestion...")

    await connect_db()

    async with httpx.AsyncClient() as client:

        # Add/edit titles here
        titles = [
            "Mission: Impossible",
            "Inception",
            "Interstellar",
            "The Dark Knight",
            "Avengers: Endgame",
        ]

        for title in titles:
            try:
                await fetch_and_save(client, title)
            except Exception as e:
                print(f"❌ Error fetching {title}: {e}")

    await close_db()

    print("\n🏁 Done.")


if __name__ == "__main__":
    asyncio.run(main())