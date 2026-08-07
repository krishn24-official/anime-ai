import asyncio
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from app.db.mongo import connect_db, get_db, close_db

async def f():
    await connect_db()
    db = get_db()
    a = await db['anime'].find({'title.english': {'$regex': 'Your Name', '$options': 'i'}}).to_list(None)
    m = await db['movies'].find({'title': {'$regex': 'Your Name', '$options': 'i'}}).to_list(None)
    print('Anime:', [(x.get('title'), x.get('year')) for x in a])
    print('Movie:', [(x.get('title'), x.get('year')) for x in m])
    await close_db()

asyncio.run(f())
