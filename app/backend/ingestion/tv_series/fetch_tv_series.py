import asyncio

import httpx

from app.db.mongo import connect_db, close_db, get_db
from app.config import OMDB_API_KEY, OMDB_BASE_URL
from app.backend.transformers.tv_series_transformer import transform_tv_series


async def fetch_and_save(client: httpx.AsyncClient, title: str):

    db = get_db()

    tv_collection = db["tv_series"]

    print(f"\n📺 Fetching: {title}")

    response = await client.get(
        OMDB_BASE_URL,
        params={
            "apikey": OMDB_API_KEY,
            "t": title,
            "type": "series",
            "plot": "full",
        },
        timeout=30.0
    )

    response.raise_for_status()
    data = response.json()

    if data.get("Response") != "True":
        print(f"❌ TV series not found: {title} ({data.get('Error')})")
        return

    formatted_series = transform_tv_series(data)

    await tv_collection.replace_one(
        {"_id": formatted_series["_id"]},
        formatted_series,
        upsert=True
    )

    print(f"✅ Saved: {formatted_series['_id']}")


async def main():

    if not OMDB_API_KEY:
        print("❌ OMDB_API_KEY not set in .env")
        return

    print("🚀 Starting TV series ingestion...")

    await connect_db()

    async with httpx.AsyncClient() as client:

        # Add/edit titles here
        titles = [
            "Loki",
            "Breaking Bad",
            "Stranger Things",
            "The Mandalorian",
            "Game of Thrones",
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