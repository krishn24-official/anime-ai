import asyncio
import io
import sys
from pathlib import Path

# Force UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.db.mongo import connect_db, get_db, close_db

async def main():
    await connect_db()
    db = get_db()
    colls = sorted(await db.list_collection_names())
    print("=" * 60)
    print(f"{'Collection':<25} {'Count':<10} {'Storage (MB)':<15}")
    print("=" * 60)
    total_mb = 0.0
    for col in colls:
        try:
            cnt = await db[col].count_documents({})
            stats = await db.command("collStats", col)
            stg = stats.get("storageSize", 0) / (1024 * 1024)
            total_mb += stg
            print(f"{col:<25} {cnt:<10} {stg:<15.2f}")
        except Exception as e:
            print(f"{col:<25} error: {e}")
    print("=" * 60)
    print(f"{'TOTAL CLUSTER STORAGE':<25} {'':<10} {total_mb:<15.2f} MB")
    print("=" * 60)

    # Check episodes for Naruto, Shippuden, Boruto
    naruto_eps = await db["episodes"].count_documents({"anime_id": "anime_naruto"})
    shippuden_eps = await db["episodes"].count_documents({"anime_id": "anime_naruto_shippuden"})
    boruto_eps = await db["episodes"].count_documents({"anime_id": "anime_boruto"})
    total_eps = await db["episodes"].count_documents({})
    print(f"\nEpisodes in DB:")
    print(f"  Naruto: {naruto_eps}/220")
    print(f"  Naruto: Shippūden: {shippuden_eps}/500")
    print(f"  Boruto: {boruto_eps}/293")
    print(f"  Total episodes: {total_eps}")

    # Check anime releases in events
    anime_events = await db["events"].count_documents({"event_type": "anime_release"})
    total_events = await db["events"].count_documents({})
    print(f"\nEvents in DB:")
    print(f"  Anime Release Events: {anime_events}")
    print(f"  Total Events: {total_events}")

    # Check lore_chunks
    lore_naruto = await db["lore_chunks"].count_documents({"series_id": "anime_naruto"})
    lore_shippuden = await db["lore_chunks"].count_documents({"series_id": "anime_naruto_shippuden"})
    lore_boruto = await db["lore_chunks"].count_documents({"series_id": "anime_boruto"})
    total_lore = await db["lore_chunks"].count_documents({})
    print(f"\nLore Chunks in DB:")
    print(f"  Naruto: {lore_naruto}")
    print(f"  Shippuden: {lore_shippuden}")
    print(f"  Boruto: {lore_boruto}")
    print(f"  Total Lore Chunks: {total_lore}")

    await close_db()

if __name__ == "__main__":
    asyncio.run(main())
