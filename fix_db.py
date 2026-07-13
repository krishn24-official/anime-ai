import asyncio
from bson import ObjectId
from app.db.mongo import connect_db, get_db

async def fix():
    await connect_db()
    db = get_db()
    for coll in ['episodes', 'chapters']:
        cursor = db[coll].find({})
        async for doc in cursor:
            if isinstance(doc.get('created_by'), ObjectId):
                await db[coll].update_one({'_id': doc['_id']}, {'$set': {'created_by': str(doc['created_by'])}})
    print('Fixed')

asyncio.run(fix())
