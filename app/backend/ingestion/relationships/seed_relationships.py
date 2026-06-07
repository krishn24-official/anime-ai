import os
import json
import asyncio

from app.db.mongo import (
    connect_db,
    close_db,
    get_relationship_collection
)


RELATIONSHIP_FOLDER = "data/relationships"


async def seed_relationships():

    await connect_db()

    relationship_collection = (
        get_relationship_collection()
    )

    total_saved = 0

    for root, dirs, files in os.walk(
        RELATIONSHIP_FOLDER
    ):

        for file in files:

            if not file.endswith(".json"):
                continue

            filepath = os.path.join(
                root,
                file
            )

            print(
                f"\n📂 Reading: {filepath}"
            )

            with open(
                filepath,
                "r",
                encoding="utf-8"
            ) as f:

                relationships = json.load(f)

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


asyncio.run(seed_relationships())