from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.services.news_pipeline_service import run_news_pipeline
from app.services.trending_service import recompute_search_trending
from app.services.release_status_sync import sync_all_release_statuses
from app.services.daily_discovery_service import run_daily_discovery

scheduler = AsyncIOScheduler()


def start_news_scheduler():
    # Run every 30 minutes — reduced from 3 min to cut memory pressure.
    # Categorization is fully source/channel-mapped, no AI calls involved.
    scheduler.add_job(
        run_news_pipeline,
        "interval",
        minutes=30,
        id="news_pipeline",
    )

    # Run every 30 minutes to recompute search trending (aligned with pipeline).
    async def _search_trending_job():
        try:
            await recompute_search_trending(hours=3)
        except Exception as e:
            print(f"[scheduler] failed to recompute search trending: {e}")

    scheduler.add_job(
        _search_trending_job,
        "interval",
        minutes=30,
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

    # NOTE: No startup create_task for release_status_sync — avoids a memory
    # spike on every deploy. It will run on its first scheduled tick (24 h).

    async def _daily_discovery_job():
        try:
            await run_daily_discovery()
        except Exception as e:
            print(f"[scheduler] failed to run daily discovery sync: {e}")

    scheduler.add_job(
        _daily_discovery_job,
        "interval",
        hours=24,
        id="daily_discovery_sync",
    )

    scheduler.start()
    print("[scheduler] News pipeline started (every 30 min)")
    print("[scheduler] Search trending started (every 30 min)")
    print("[scheduler] Release status sync scheduled (every 24 h)")
    print("[scheduler] Daily discovery sync scheduled (every 24 h)")


def stop_news_scheduler():
    scheduler.shutdown(wait=False)