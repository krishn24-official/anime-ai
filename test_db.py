import asyncio
from app.db.mongo import connect_db, close_db
from app.repositories.news_repository import get_latest_news

async def main():
    await connect_db()
    latest = await get_latest_news(5)
    for l in latest:
        print(l.get("published_at"))
    await close_db()

asyncio.run(main())
