import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath('.'))

from app.db.mongo import connect_db, close_db, get_db

async def main():
    await connect_db()
    db = get_db()
    actor = await db['actors'].find_one({'name': 'Mahesh Babu'})
    if actor:
        print(f"Birthdate in DB: '{actor.get('birthdate')}'")
    else:
        print("Actor not found")
    await close_db()

if __name__ == '__main__':
    asyncio.run(main())
