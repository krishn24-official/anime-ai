import json
import asyncio
from pathlib import Path

from app.db.mongo import (
    connect_db,
    close_db,
    get_db
)


EVENTS_DIR = Path(
    "data/events"
)


async def seed_events():

    await connect_db()

    db = get_db()

    event_files = (
        EVENTS_DIR.glob("*.json")
    )

    total = 0

    for file_path in event_files:

        print(
            f"\n📂 Reading: {file_path}"
        )

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as f:

            events = json.load(f)

        for event in events:

            await (
                db["events"]
                .replace_one(
                    {
                        "_id":
                        event["_id"]
                    },
                    event,
                    upsert=True
                )
            )

            total += 1

    print(
        f"\n✅ Seeded {total} events"
    )

    await close_db()


if __name__ == "__main__":

    asyncio.run(
        seed_events()
    )