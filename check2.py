import asyncio
from app.db.mongo import connect_db, get_db, close_db

async def main():
    await connect_db()
    db = get_db()
    movie = await db['movies'].find_one()
    anime = await db['anime'].find_one()
    
    print("Movie title field:", type(movie.get("title")), movie.get("title"))
    print("Anime title field:", type(anime.get("title")), anime.get("title"))
    
    await close_db()

if __name__ == '__main__':
    asyncio.run(main())
