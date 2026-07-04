from datetime import datetime, timedelta

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

async def get_events_by_date_range(start_date: str, end_date: str):
    db = get_db()
    
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        return []
        
    if end_dt < start_dt:
        return []
        
    days = (end_dt - start_dt).days
    if days > 366:
        days = 366
        
    date_criteria = []
    for i in range(days + 1):
        dt = start_dt + timedelta(days=i)
        date_criteria.append({"month": dt.month, "day": dt.day})
        
    if not date_criteria:
        return []
        
    return await (
        db["events"]
        .find(
            {
                "$or": date_criteria,
                "is_deleted": False
            }
        )
        .to_list(None)
    )