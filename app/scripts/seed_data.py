import os
import glob
import json
import asyncio
from app.db.mongo import connect_db, get_db


def get_glob_files(folder_path: str):
    import glob
    return glob.glob(os.path.join(folder_path, "*.json"))


def load_json_file(file_path: str):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


# Seed one collection from multiple files
async def seed_collection(folder_path, collection_name):
    db = get_db()

    files = await asyncio.to_thread(get_glob_files, folder_path)

    if not files:
        print(f"No files found in {folder_path}")
        return

    for file in files:
        try:
            data = await asyncio.to_thread(load_json_file, file)

            items = data if isinstance(data, list) else [data]
            for item in items:
                try:
                    await db[collection_name].replace_one(
                        {"_id": item["_id"]},
                        item,
                        upsert=True,
                    )
                except Exception as exc:
                    print(f"Failed to upsert item in {collection_name}: {exc}")

            print(f"Seeded {collection_name} from {os.path.basename(file)}")

        except Exception as e:
            print(f"Error in {file}: {e}")


# Main seeder
async def seed_all():
    await connect_db()
    db = get_db()

    print("Using DB:", db.name)

    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data"))

    await seed_collection(os.path.join(BASE_DIR, "characters"), "characters")
    await seed_collection(os.path.join(BASE_DIR, "anime"), "anime")
    await seed_collection(os.path.join(BASE_DIR, "episodes"), "episodes")
    await seed_collection(os.path.join(BASE_DIR, "manga"), "manga")
    await seed_collection(os.path.join(BASE_DIR, "chapters"), "chapters")
    await seed_collection(os.path.join(BASE_DIR, "relationships"), "relationships")
    await seed_collection(os.path.join(BASE_DIR, "voice_actors"), "voice_actors")
    await seed_collection(os.path.join(BASE_DIR, "organizations"), "organizations")

    print("Seeding complete")


if __name__ == "__main__":
    asyncio.run(seed_all())