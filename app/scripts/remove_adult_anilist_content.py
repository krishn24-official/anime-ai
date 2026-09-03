import asyncio
import sys
import io

# Fix Windows console encoding for emoji / CJK
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from app.db.mongo import connect_db, close_db, get_db

async def clean_characters_for_anime(db, anime_id: str):
    """Remove the given anime_id from all characters. Delete character if it was their only anime."""
    # Find all characters that have this anime in their anime_ids
    cursor = db["characters"].find({"anime_ids": anime_id})
    characters = await cursor.to_list(length=None)
    
    deleted = 0
    updated = 0
    
    for char in characters:
        current_ids = char.get("anime_ids", [])
        if anime_id in current_ids:
            current_ids.remove(anime_id)
            
            if not current_ids:
                # Character has no more anime, delete them
                await db["characters"].delete_one({"_id": char["_id"]})
                deleted += 1
            else:
                # Update character with removed ID
                await db["characters"].update_one(
                    {"_id": char["_id"]},
                    {"$set": {"anime_ids": current_ids}}
                )
                updated += 1
                
    return deleted, updated

async def main():
    print("Connecting to MongoDB...")
    await connect_db()
    db = get_db()
    
    try:
        # 1. Anime
        anime_cursor = db["anime"].find({"genres": "Hentai"})
        adult_animes = await anime_cursor.to_list(length=None)
        
        print(f"Found {len(adult_animes)} adult anime to delete.")
        total_chars_deleted = 0
        total_chars_updated = 0
        
        for anime in adult_animes:
            anime_id = anime["_id"]
            title = anime.get("title", {}).get("english") or anime.get("title", {}).get("romaji")
            print(f"Processing Anime: {title} ({anime_id})")
            
            # Clean up characters
            c_del, c_upd = await clean_characters_for_anime(db, anime_id)
            total_chars_deleted += c_del
            total_chars_updated += c_upd
            
            # Delete the anime itself
            await db["anime"].delete_one({"_id": anime_id})
            
        print(f"Finished anime. Deleted {total_chars_deleted} characters, updated {total_chars_updated} characters.")
        
        # 2. Manga
        manga_cursor = db["manga"].find({"genres": "Hentai"})
        adult_mangas = await manga_cursor.to_list(length=None)
        
        print(f"Found {len(adult_mangas)} adult manga to delete.")
        for manga in adult_mangas:
            manga_id = manga["_id"]
            title = manga.get("title", {}).get("english") or manga.get("title", {}).get("romaji")
            print(f"Deleting Manga: {title} ({manga_id})")
            await db["manga"].delete_one({"_id": manga_id})
            
        print("Cleanup of Anilist adult content complete!")
    finally:
        await close_db()

if __name__ == "__main__":
    asyncio.run(main())
