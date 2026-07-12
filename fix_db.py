import asyncio
from app.db.mongo import get_db, connect_db
from bson import ObjectId

async def fix():
    await connect_db()
    db = get_db()
    doc = await db['anime'].find_one({'_id': 'anime_one_piece_heroines'})
    if doc and 'updated_by' in doc.get('source_metadata', {}):
        val = doc['source_metadata']['updated_by']
        if isinstance(val, ObjectId):
            await db['anime'].update_one({'_id': doc['_id']}, {'$set': {'source_metadata.updated_by': str(val)}})
            print('Fixed updated_by')
    if doc and 'created_by' in doc.get('source_metadata', {}):
        val = doc['source_metadata']['created_by']
        if isinstance(val, ObjectId):
            await db['anime'].update_one({'_id': doc['_id']}, {'$set': {'source_metadata.created_by': str(val)}})
            print('Fixed created_by')
            
asyncio.run(fix())
