import asyncio
from app.db.mongo import connect_db, get_db

async def main():
    await connect_db()
    db = get_db()
    cursor = await db['movies'].aggregate([
        {
            '$match': {
                'title': {'$regex': 'war', '$options': 'i'},
                'is_deleted': {'$ne': True}
            }
        },
        {
            '$addFields': {
                'title_length': {'$strLenCP': {'$ifNull': ['$title', '']}}
            }
        },
        {
            '$sort': {'title_length': 1}
        },
        {
            '$limit': 10
        }
    ])
    res = await cursor.to_list(length=None)
    print([r['title'] for r in res])

if __name__ == '__main__':
    asyncio.run(main())
