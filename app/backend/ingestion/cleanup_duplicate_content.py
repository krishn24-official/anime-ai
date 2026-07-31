import asyncio
import sys
import io

# Fix Windows console encoding for emoji / CJK
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from app.db.mongo import connect_db, close_db, get_db

async def cleanup_collection(db, collection_name: str, has_dict_title: bool = False):
    print(f"\n🔍 Looking for duplicate {collection_name}...")
    cursor = db[collection_name].find({"is_deleted": {"$ne": True}})
    items = await cursor.to_list(length=None)
    
    # Group by canonical title (lowercase, stripped)
    title_map = {}
    for item in items:
        title = item.get("title")
        if not title:
            continue
            
        canonical_title = None
        if has_dict_title and isinstance(title, dict):
            # Prefer english, then romaji
            t = title.get("english") or title.get("romaji") or title.get("japanese")
            if t:
                canonical_title = str(t).strip().lower()
        else:
            canonical_title = str(title).strip().lower()
            
        if not canonical_title:
            continue
            
        if canonical_title not in title_map:
            title_map[canonical_title] = []
        title_map[canonical_title].append(item)
        
    duplicates_found = 0
    merged_count = 0
        
    for canonical_title, group in title_map.items():
        if len(group) > 1:
            duplicates_found += 1
            print(f"Found {len(group)} items matching '{canonical_title}'")
            
            # Sort so the one with the shortest ID (usually the original) is first
            group.sort(key=lambda x: len(str(x["_id"])))
            
            primary = group[0]
            primary_id = primary["_id"]
            
            for duplicate in group[1:]:
                duplicate_id = duplicate["_id"]
                print(f"  Merging {duplicate_id} into {primary_id}")
                
                # Merge data if missing in primary (can be extended based on need)
                update_data = {}
                
                if "source_metadata" not in primary and "source_metadata" in duplicate:
                    update_data["source_metadata"] = duplicate["source_metadata"]
                
                if not primary.get("plot") and duplicate.get("plot"):
                    update_data["plot"] = duplicate["plot"]
                if not primary.get("year") and duplicate.get("year"):
                    update_data["year"] = duplicate["year"]
                if not primary.get("genres") and duplicate.get("genres"):
                    update_data["genres"] = duplicate["genres"]
                if not primary.get("poster") and duplicate.get("poster"):
                    update_data["poster"] = duplicate["poster"]
                if not primary.get("backdrop") and duplicate.get("backdrop"):
                    update_data["backdrop"] = duplicate["backdrop"]
                    
                if update_data:
                    await db[collection_name].update_one(
                        {"_id": primary_id},
                        {"$set": update_data}
                    )
                
                # Finally, delete the duplicate item
                await db[collection_name].delete_one({"_id": duplicate_id})
                merged_count += 1
                
    print(f"✅ Finished! Merged {merged_count} duplicate records across {duplicates_found} titles in {collection_name}.")

async def cleanup_duplicates():
    await connect_db()
    db = get_db()
    
    await cleanup_collection(db, "movies", has_dict_title=False)
    await cleanup_collection(db, "tv_series", has_dict_title=False)
    await cleanup_collection(db, "anime", has_dict_title=True)
    await cleanup_collection(db, "manga", has_dict_title=True)
    
    await close_db()

if __name__ == "__main__":
    asyncio.run(cleanup_duplicates())
