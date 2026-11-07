from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.events import EVENT_JOB_ERROR

from app.services.news_pipeline_service import run_news_pipeline
from app import container
from app.config import ATLAS_STORAGE_LIMIT_MB, SEARCH_CATALOG_REBUILD_HOURS
from app.container import trending_service
from app.services.release_status_sync import sync_all_release_statuses
from app.services.daily_discovery_service import run_daily_discovery

scheduler = AsyncIOScheduler()


def _job_error_listener(event):
    if event.exception:
        print(f"[scheduler] Job {event.job_id} encountered error: {event.exception}")


scheduler.add_listener(_job_error_listener, EVENT_JOB_ERROR)


def start_news_scheduler():
    # Run immediately on startup in background, and then every 30 minutes
    scheduler.add_job(
        run_news_pipeline,
        "interval",
        minutes=30,
        next_run_time=datetime.now(),
        id="news_pipeline",
    )

    # Run every 30 minutes to recompute search trending (aligned with pipeline).
    async def _search_trending_job():
        try:
            await trending_service().recompute_search_trending(hours=3)
        except Exception as e:
            print(f"[scheduler] failed to recompute search trending: {e}")

    scheduler.add_job(
        _search_trending_job,
        "interval",
        minutes=30,
        next_run_time=datetime.now() + timedelta(seconds=10),
        id="search_trending_recompute",
    )

    # Run every 30 minutes to recompute news mention trending from RSS article scans
    async def _news_trending_job():
        try:
            res = await trending_service().recompute_news_trending(hours=48)
            print(f"[scheduler] News trending recompute: {res}")
        except Exception as e:
            print(f"[scheduler] failed to recompute news trending: {e}")

    scheduler.add_job(
        _news_trending_job,
        "interval",
        minutes=30,
        next_run_time=datetime.now() + timedelta(seconds=20),
        id="news_trending_recompute",
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
        next_run_time=datetime.now() + timedelta(seconds=15),
        id="daily_discovery_sync",
    )

    # Rebuild the search catalog so items added by ingestion / TMDb sync become
    # searchable via Atlas. Admin edits are synced immediately (keeps_search_in_sync).
    # First run after one interval (no startup memory spike), and only once the
    # Atlas index has been set up with app/scripts/build_search_catalog.py.
    async def _search_catalog_job():
        try:
            if not container.search_catalog_enabled():
                return
            catalog = container.search_catalog()
            if await catalog.index_status() is None:
                return
            # Never fill the cluster: Atlas blocks all writes at the quota.
            await catalog.check_quota(ATLAS_STORAGE_LIMIT_MB)
            res = await catalog.rebuild()
            print(f"[scheduler] Search catalog rebuild: {res}")
        except Exception as e:
            print(f"[scheduler] failed to rebuild search catalog: {e}")

    scheduler.add_job(
        _search_catalog_job,
        "interval",
        hours=SEARCH_CATALOG_REBUILD_HOURS,
        id="search_catalog_rebuild",
    )

    scheduler.start()
    print("[scheduler] News pipeline started (every 30 min)")
    print("[scheduler] Search trending started (every 30 min)")
    print("[scheduler] Release status sync scheduled (every 24 h)")
    print("[scheduler] Daily discovery sync scheduled (every 24 h)")


def stop_news_scheduler():
    scheduler.shutdown(wait=False)
