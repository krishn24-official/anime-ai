"""
One-time script to extract game properties for all existing characters
in the DB using Gemini. Run this once after setting up game_properties.py.

After this, new characters ingested via fetch_character_by_name.py will
get game_properties automatically.

Run:
    python -m app.backend.ingestion.anime.extract_game_properties
"""
import asyncio

from app.db.mongo import connect_db, close_db, get_db
from app.services.game_property_extractor import extract_game_properties


async def process_character(col, character: dict) -> bool:
    name = character.get("name", "")
    description = character.get("description", "")
    gender = character.get("gender")
    anime_ids = character.get("anime_ids", [])
    existing = character.get("game_properties", [])

    # Skip if already processed
    if existing:
        print(f"  Skipping (already has {len(existing)} properties): {name}")
        return False

    if not description:
        print(f"  No description, skipping: {name}")
        return False

    print(f"  Extracting: {name}")

    properties = await extract_game_properties(
        character_name=name,
        description=description,
        gender=gender,
        anime_ids=anime_ids,
    )

    if properties:
        await col.update_one(
            {"_id": character["_id"]},
            {"$set": {"game_properties": properties}}
        )
        print(f"  {name}: {properties}")
    else:
        print(f"  No properties extracted: {name}")

    return True


async def main():
    print("Starting game property extraction...")

    await connect_db()

    db = get_db()
    col = db["characters"]

    # Fetch all characters
    characters = await col.find(
        {},
        {
            "_id": 1,
            "name": 1,
            "description": 1,
            "gender": 1,
            "anime_ids": 1,
            "game_properties": 1,
        }
    ).to_list(None)

    print(f"Found {len(characters)} characters\n")

    processed = 0
    skipped = 0

    for character in characters:
        was_processed = await process_character(col, character)

        if was_processed:
            processed += 1
            # gemini-2.0-flash: 15 RPM free tier
            # 5s between calls = 12 RPM, safe margin
            await asyncio.sleep(5)
        else:
            skipped += 1

    await close_db()

    print(f"\nDone. Processed: {processed}, Skipped: {skipped}")


if __name__ == "__main__":
    asyncio.run(main())