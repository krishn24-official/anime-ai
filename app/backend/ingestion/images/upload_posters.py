"""
Upload poster images already stored in MongoDB (from OMDb fetch) to
Cloudinary and update the `images.poster` field with the Cloudinary URL.

Run:
    python -m app.backend.ingestion.images.upload_posters
"""
import asyncio

from app.db.mongo import connect_db, close_db, get_db
from app.services.cloudinary_service import upload_image_from_url


COLLECTIONS_CONFIG = [
    {
        "collection": "movies",
        "folder": "entertainment_hub/movies",
        "id_prefix": "movie",
        "image_field": "images.poster",
    },
    {
        "collection": "tv_series",
        "folder": "entertainment_hub/tv_series",
        "id_prefix": "tv",
        "image_field": "images.poster",
    },
    {
        "collection": "anime",
        "folder": "entertainment_hub/anime",
        "id_prefix": "anime",
        "image_field": "images.poster",
    },
    {
        "collection": "characters",
        "folder": "entertainment_hub/characters",
        "id_prefix": "char",
        "image_field": "images.profile",   # characters use profile, not poster
    },
]


async def upload_posters_for_collection(
    collection_name: str,
    folder: str,
    id_prefix: str,
    image_field: str,
):
    db = get_db()
    col = db[collection_name]

    # image_field is dot-notation e.g. "images.poster" or "images.profile"
    docs = await col.find(
        {image_field: {"$exists": True, "$ne": None}},
        {"_id": 1, "images": 1, "title": 1, "name": 1}
    ).to_list(None)

    print(f"\n📦 {collection_name} ({image_field}): {len(docs)} docs with image")

    # Parse dot-notation to extract nested value
    field_keys = image_field.split(".")

    for doc in docs:
        doc_id = doc["_id"]

        # Traverse nested field: images -> poster/profile
        value = doc
        for key in field_keys:
            value = (value or {}).get(key)

        image_url = value

        if not image_url:
            continue

        # Skip if already a Cloudinary URL
        if "cloudinary.com" in str(image_url):
            print(f"  ⏭ Already on Cloudinary: {doc_id}")
            continue

        public_id = f"{id_prefix}_{doc_id}_{field_keys[-1]}".replace("/", "_")

        print(f"  ⬆ Uploading {doc_id}...")

        cloudinary_url = await upload_image_from_url(
            image_url,
            folder=folder,
            public_id=public_id,
        )

        if cloudinary_url:
            await col.update_one(
                {"_id": doc_id},
                {"$set": {image_field: cloudinary_url}}
            )
            print(f"  ✅ Updated: {doc_id} → {cloudinary_url}")
        else:
            print(f"  ❌ Failed: {doc_id}")


async def main():
    print("🚀 Starting poster upload to Cloudinary...")

    await connect_db()

    for config in COLLECTIONS_CONFIG:
        await upload_posters_for_collection(
            config["collection"],
            config["folder"],
            config["id_prefix"],
            config["image_field"],
        )

    await close_db()

    print("\n🏁 Done.")


if __name__ == "__main__":
    asyncio.run(main())