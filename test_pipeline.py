import asyncio
from app.db.mongo import connect_db, close_db
from app.services.news_pipeline_service import run_news_pipeline
from app.db.setup_collections import create_collections
from app.db.indexes import create_indexes

async def main():
    await connect_db()
    # It might be an issue with inserting, so we run the pipeline
    summary = await run_news_pipeline()
    print("SUMMARY:", summary)
    await close_db()

asyncio.run(main())
