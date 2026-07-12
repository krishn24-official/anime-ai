from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.services.news_pipeline_service import run_news_pipeline
from app.services.trending_service import recompute_search_trending
from app.services.release_status_sync import sync_all_release_statuses

scheduler = AsyncIOScheduler()


def start_news_scheduler():
    # Run every 5 minutes. Categorization is fully source/channel-mapped,
    # no AI calls involved.
    scheduler.add_job(
        run_news_pipeline,
        "interval",
        minutes=3,
        id="news_pipeline",
    )
    
    # Run every 15 minutes to recompute search trending
    async def _search_trending_job():
        try:
            await recompute_search_trending(hours=3)
        except Exception as e:
            print(f"[scheduler] failed to recompute search trending: {e}")
            
    scheduler.add_job(
        _search_trending_job,
        "interval",
        minutes=15,
        id="search_trending_recompute",
    )
    
    async def _release_status_sync_job():
        try:
            res = await sync_all_release_statuses()
            print(f"[scheduler] Release status sync: {res}")
        except Exception as e:
            print(f"[scheduler] failed to sync release statuses: {e}")
            
    scheduler.add_job(
        _release_status_sync_job,
        "interval",
        hours=24,
        id="release_status_sync",
    )
    
    # Run it once immediately on startup
    import asyncio
    asyncio.create_task(_release_status_sync_job())
    
    scheduler.start()
    print("🕒 News pipeline scheduler started (every 5 min)")
    print("🕒 Search trending scheduler started (every 15 min)")
    print("🕒 Release status sync scheduled (every 24 hours)")


def stop_news_scheduler():
    scheduler.shutdown(wait=False)