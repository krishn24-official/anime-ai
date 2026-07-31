import asyncio
import sys
import io

# Fix Windows console encoding for emoji / CJK
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from app.db.mongo import connect_db, close_db, get_db

async def cleanup_duplicates():
    await connect_db()
    db = get_db()
    
    print("🔍 Looking for duplicate actors...")
    actors_cursor = db["actors"].find({"is_deleted": False})
    
    actors = await actors_cursor.to_list(length=None)
    
    # Group by canonical name (lowercase, stripped)
    name_map = {}
    for actor in actors:
        name = actor.get("name")
        if not name:
            continue
            
        canonical_name = name.strip().lower()
        if canonical_name not in name_map:
            name_map[canonical_name] = []
        name_map[canonical_name].append(actor)
        
    duplicates_found = 0
    merged_count = 0
        
    for canonical_name, group in name_map.items():
        if len(group) > 1:
            duplicates_found += 1
            print(f"Found {len(group)} actors matching '{canonical_name}'")
            
            # Sort so the one with the shortest ID (usually the original) is first
            group.sort(key=lambda x: len(x["_id"]))
            
            primary = group[0]
            primary_id = primary["_id"]
            
            for duplicate in group[1:]:
                duplicate_id = duplicate["_id"]
                print(f"  Merging {duplicate_id} into {primary_id}")
                
                # Merge data if missing in primary
                update_data = {}
                if not primary.get("tmdb_id") and duplicate.get("tmdb_id"):
                    update_data["tmdb_id"] = duplicate["tmdb_id"]
                if not primary.get("birthdate") and duplicate.get("birthdate"):
                    update_data["birthdate"] = duplicate["birthdate"]
                if not primary.get("biography") and duplicate.get("biography"):
                    update_data["biography"] = duplicate["biography"]
                if not primary.get("images", {}).get("profile") and duplicate.get("images", {}).get("profile"):
                    update_data["images.profile"] = duplicate["images"]["profile"]
                    
                if update_data:
                    await db["actors"].update_one(
                        {"_id": primary_id},
                        {"$set": update_data}
                    )
                    # Update primary object in memory for next iterations
                    for k, v in update_data.items():
                        if k == "images.profile":
                            if "images" not in primary:
                                primary["images"] = {}
                            primary["images"]["profile"] = v
                        else:
                            primary[k] = v
                
                # Replace the duplicate actor ID with the primary actor ID in movies/tv series
                await db["movies"].update_many(
                    {"cast.actor_id": duplicate_id},
                    {"$set": {"cast.$[elem].actor_id": primary_id}},
                    array_filters=[{"elem.actor_id": duplicate_id}]
                )
                await db["movies"].update_many(
                    {"director.actor_id": duplicate_id},
                    {"$set": {"director.$[elem].actor_id": primary_id}},
                    array_filters=[{"elem.actor_id": duplicate_id}]
                )
                
                await db["tv_series"].update_many(
                    {"cast.actor_id": duplicate_id},
                    {"$set": {"cast.$[elem].actor_id": primary_id}},
                    array_filters=[{"elem.actor_id": duplicate_id}]
                )
                await db["tv_series"].update_many(
                    {"creators.actor_id": duplicate_id},
                    {"$set": {"creators.$[elem].actor_id": primary_id}},
                    array_filters=[{"elem.actor_id": duplicate_id}]
                )
                
                # Finally, delete the duplicate actor
                await db["actors"].delete_one({"_id": duplicate_id})
                merged_count += 1
                
    print(f"\n✅ Finished! Merged {merged_count} duplicate records across {duplicates_found} names.")
    await close_db()

if __name__ == "__main__":
    asyncio.run(cleanup_duplicates())
