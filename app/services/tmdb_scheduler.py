from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.services.tmdb_sync_service import run_tmdb_sync

scheduler = AsyncIOScheduler()


def start_tmdb_scheduler():
    # Sync trending movies/TV once a day
    scheduler.add_job(
        run_tmdb_sync,
        "interval",
        hours=24,
        id="tmdb_sync",
        kwargs={"pages": 1},
    )
    scheduler.start()
    print("🎬 TMDB sync scheduler started (every 24h)")


def stop_tmdb_scheduler():
    scheduler.shutdown(wait=False)