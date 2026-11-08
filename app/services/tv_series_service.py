from app.repositories.tv_series_repository import get_all_tv_series, get_tv_series_by_id
from app.services.search_listing import ranked_documents


def _serialize(series: dict) -> dict:
    series = dict(series)
    series["id"] = series.pop("_id")
    return series


async def fetch_all_tv_series(page: int = 1, limit: int = 20, search: str = None):
    if search:  # ranked by relevance, same as the global search bar
        series_list, total = await ranked_documents("tv_series", search, limit, (page - 1) * limit)
    else:
        series_list, total = await get_all_tv_series(page=page, limit=limit)

    return {
        "items": [_serialize(s) for s in series_list],
        "total": total,
        "page": page,
        "limit": limit,
    }


async def fetch_tv_series(series_id: str):
    series = await get_tv_series_by_id(series_id)
    if not series or series.get("is_deleted"):  # deleted titles are not public
        return None
    return _serialize(series)
