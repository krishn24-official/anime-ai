from datetime import datetime

from app.db.mongo import get_db


async def get_today_events():

    db = get_db()

    today = datetime.utcnow()

    return await (
        db["events"]
        .find(
            {
                "month": today.month,
                "day": today.day,
                "is_deleted": False
            }
        )
        .to_list(None)
    )