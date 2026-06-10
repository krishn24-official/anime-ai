import os
import json
import asyncio

from app.db.mongo import (
    connect_db,
    close_db,
    get_relationship_collection
)


RELATIONSHIP_FOLDER = "data/relationships"


def load_json_file(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def get_json_files(folder: str):
    json_files = []
    for root, _, files in os.walk(folder):
        for file in files:
            if file.endswith(".json"):
                json_files.append(os.path.join(root, file))
    return json_files


async def seed_relationships():

    await connect_db()

    relationship_collection = (
        get_relationship_collection()
    )

    total_saved = 0

    filepaths = await asyncio.to_thread(get_json_files, RELATIONSHIP_FOLDER)

    for filepath in filepaths:

        print(
            f"\n📂 Reading: {filepath}"
        )

        relationships = await asyncio.to_thread(load_json_file, filepath)

        for relationship in relationships:

            await relationship_collection.replace_one(
                {
                    "_id": relationship["_id"]
                },
                relationship,
                upsert=True
            )

            total_saved += 1

            print(
                f"✅ Saved: {relationship['_id']}"
            )

    print(
        f"\n🎉 Total relationships saved: {total_saved}"
    )

    await close_db()


if __name__ == "__main__":
    asyncio.run(seed_relationships())