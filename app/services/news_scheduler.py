from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.services.news_pipeline_service import run_news_pipeline

scheduler = AsyncIOScheduler()


def start_news_scheduler():
    # Run every 30 minutes. Categorization is fully source/channel-mapped,
    # no AI calls involved.
    scheduler.add_job(
        run_news_pipeline,
        "interval",
        minutes=30,
        id="news_pipeline",
    )
    scheduler.start()
    print("🕒 News pipeline scheduler started (every 30 min)")


def stop_news_scheduler():
    scheduler.shutdown(wait=False)