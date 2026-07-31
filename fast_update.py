import asyncio
from app.db.mongo import connect_db, close_db, get_db
from app.backend.ingestion.tmdb_client import get_movie_details, close_client
from app.backend.ingestion.tmdb_mapper import _extract_us_theatrical_release_date

async def main():
    await connect_db()
    db = get_db()
    
    titles_to_fix = [
        'Trap', 
        'Teenage Mutant Ninja Turtles: Mutant Mayhem',
        'Descendants',
        'Fast & Furious Presents: Hobbs & Shaw',
        'Harold and the Purple Crayon',
        'Red Sonja',
        'Spider-Man: Brand New Day',
        'The Amazing Spider-Man',
        'The Amazing Spider-Man 2'
    ]
    
    for title in titles_to_fix:
        movie = await db['movies'].find_one({'title': title})
        if not movie:
            print(f'Not found: {title}')
            continue
        tmdb_id = movie.get('source_metadata', {}).get('tmdb_id')
        if not tmdb_id:
            continue
            
        details = await get_movie_details(tmdb_id)
        if not details: continue
        
        actual = _extract_us_theatrical_release_date(details)
        year = (actual or '')[:4] or None
        
        if actual != movie.get('release_date'):
            print(f'Updating {title}: {movie.get("release_date")} -> {actual}')
            await db['movies'].update_one(
                {'_id': movie['_id']},
                {'$set': {'release_date': actual, 'year': year}}
            )
        else:
            print(f'No change for {title}: {actual}')

    await close_client()
    await close_db()
asyncio.run(main())
