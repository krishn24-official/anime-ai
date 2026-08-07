import asyncio
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from app.db.mongo import connect_db, close_db, get_db
from app.services.duplicate_detection_service import check_for_duplicate

async def main():
    print("Starting cross-collection duplicate audit...")
    await connect_db()
    db = get_db()
    
    # 1. Audit Anime collection
    print("\n=== Auditing Anime ===")
    cursor = db["anime"].find({"is_deleted": {"$ne": True}})
    total = await db["anime"].count_documents({"is_deleted": {"$ne": True}})
    
    count = 0
    found = 0
    async for doc in cursor:
        count += 1
        dup = await check_for_duplicate(doc, "anime")
        if dup:
            found += 1
            title = doc.get("title", {}).get("english") or doc.get("title", {}).get("romaji")
            print(f"[DUPLICATE] anime: '{title}' ({doc['_id']}, {doc.get('year')}) "
                  f"-> matches {dup['content_type']}: {dup['content_id']}")
            
            await db["anime"].update_one(
                {"_id": doc["_id"]},
                {"$set": {"possible_duplicate_of": dup}}
            )
            
        if count % 100 == 0:
            print(f"Processed {count}/{total} anime...")
            
    print(f"Done auditing anime. Found {found} possible duplicates.")
    
    # 2. Audit Movies collection
    # Note: the user request said "For every anime document, normalize its title ... and compare against every movie document's normalized title". 
    # Technically checking anime covers the links, but a movie might duplicate a tv series.
    # The prompt explicitly asked to run it for existing duplicates (anime vs movies mostly).
    # Doing anime covers anime<->movies and anime<->tv_series. 
    # Let's also check movies vs tv_series just in case, or just stick to Anime.
    print("\nAudit Complete.")
    await close_db()

if __name__ == "__main__":
    asyncio.run(main())
