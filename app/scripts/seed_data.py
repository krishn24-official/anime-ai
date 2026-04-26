import os
import glob
import json
import asyncio
from app.db.mongo import connect_db, get_db


# 🔥 Seed one collection from multiple files
async def seed_collection(folder_path, collection_name):
    db = get_db()

    files = glob.glob(os.path.join(folder_path, "*.json"))

    if not files:
        print(f"⚠️ No files found in {folder_path}")
        return

    for file in files:
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                for item in data:
                    try:
                        await db[collection_name].insert_one(item)
                    except Exception:
                        pass  # skip duplicates

            print(f"✅ Seeded {collection_name} from {os.path.basename(file)}")

        except Exception as e:
            print(f"❌ Error in {file}: {e}")


# 🔥 Main seeder
async def seed_all():
    await connect_db()
    db = get_db()

    print("🔥 USING DB:", db.name)

    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data"))

    await seed_collection(os.path.join(BASE_DIR, "characters"), "characters")
    await seed_collection(os.path.join(BASE_DIR, "anime"), "anime")
    await seed_collection(os.path.join(BASE_DIR, "episodes"), "episodes")
    await seed_collection(os.path.join(BASE_DIR, "manga"), "manga")
    await seed_collection(os.path.join(BASE_DIR, "chapters"), "chapters")
    await seed_collection(os.path.join(BASE_DIR, "relationships"), "relationships")
    await seed_collection(os.path.join(BASE_DIR, "voice_actors"), "voice_actors")

    print("🚀 Seeding complete")


if __name__ == "__main__":
    asyncio.run(seed_all())