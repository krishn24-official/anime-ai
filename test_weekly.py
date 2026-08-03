import asyncio
from app.db.mongo import get_db, connect_db, close_db
import json
from bson import json_util
from app.repositories.content_repository import get_weekly_suggestions

async def main():
    await connect_db()
    res = await get_weekly_suggestions(2)
    print(json.dumps(res, indent=2))
    await close_db()

asyncio.run(main())
