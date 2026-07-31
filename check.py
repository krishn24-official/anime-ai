import asyncio
from app.db.mongo import connect_db, get_db, close_db

async def main():
    await connect_db()
    db = get_db()
    actors = await db['actors'].find({'name': {'$regex': 'Ranveer Singh', '$options': 'i'}}).to_list(None)
    for a in actors:
        print(f"ID: {a['_id']}, Name: '{a['name']}', Deleted: {a.get('is_deleted')}, TMDB ID: {a.get('tmdb_id')}")
    
    # Also let's check total actors
    total = await db['actors'].count_documents({})
    deleted = await db['actors'].count_documents({'is_deleted': True})
    print(f"Total: {total}, Deleted: {deleted}")
    
    await close_db()

if __name__ == '__main__':
    asyncio.run(main())
