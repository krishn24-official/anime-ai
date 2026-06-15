from app.repositories.tv_series_repository import get_all_tv_series, get_tv_series_by_id


def _serialize(series: dict) -> dict:
    series = dict(series)
    series["id"] = series.pop("_id")
    return series


async def fetch_all_tv_series(page: int = 1, limit: int = 20):
    series_list, total = await get_all_tv_series(page=page, limit=limit)

    return {
        "items": [_serialize(s) for s in series_list],
        "total": total,
        "page": page,
        "limit": limit,
    }


async def fetch_tv_series(series_id: str):
    series = await get_tv_series_by_id(series_id)
    if not series:
        return None
    return _serialize(series)