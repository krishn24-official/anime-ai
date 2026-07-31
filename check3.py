import asyncio
from app.db.mongo import connect_db, close_db
from app.services.actors_service import search_actor

async def main():
    await connect_db()
    results = await search_actor('hrit')
    print("Results length:", len(results))
    print(results)
    await close_db()

if __name__ == '__main__':
    asyncio.run(main())
