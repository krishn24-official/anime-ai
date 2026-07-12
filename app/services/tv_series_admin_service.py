from datetime import datetime, timezone
from app.backend.utils.slug import create_slug
from app.repositories import tv_series_repository
from app.services.cloudinary_service import upload_image_from_bytes
from app.services.release_date_utils import parse_release_date

async def create_tv_series(
    admin_id: str,
    title: str,
    original_title: str | None,
    released: bool,
    status_value: str,
    start_day: int | None,
    start_month: int | None,
    start_year: int | None,
    start_precision: str,
    end_day: int | None,
    end_month: int | None,
    end_year: int | None,
    end_precision: str | None,
    total_seasons: int | None,
    total_episodes: int | None,
    episode_runtime_minutes: int | None,
    genres: list[str],
    creators: list[str],
    plot: str | None,
    language: list[str],
    country: list[str],
    tagline: str | None,
    trailer_url: str | None,
    poster_bytes: bytes | None,
    backdrop_bytes: bytes | None
):
    if not title:
        raise ValueError("Title must be provided")
        
    slug = create_slug(title)
    content_id = f"tv_{slug}"
    
    existing = await tv_series_repository.find_tv_series_by_slug(slug)
    if existing:
        raise ValueError(f"A TV series with this title already exists (content_id: {content_id}). Edit the existing entry instead, or use a more specific title.")
        
    if released and status_value not in ["Returning Series", "Ended", "Canceled"]:
        raise ValueError("Invalid status for released TV series")
    if not released and status_value not in ["Planned", "In Production", "Pilot"]:
        raise ValueError("Invalid status for unreleased TV series")
        
    status = status_value
    
    start_date_obj = parse_release_date(start_day, start_month, start_year, start_precision)
    first_air_date = None
    first_air_precision = None
    
    if released and start_precision != "day":
        raise ValueError("A released TV series must have day precision for its start date.")
        
    if start_precision == "day":
        first_air_date = f"{start_year}-{str(start_month).zfill(2)}-{str(start_day).zfill(2)}"
    else:
        first_air_precision = {
            "year": start_year,
            "month": start_month,
            "day": None,
            "precision": start_precision
        }
        
    last_air_date = None
    last_air_precision = None
    
    if end_precision is not None:
        end_date_obj = parse_release_date(end_day, end_month, end_year, end_precision)
        
        start_cmp = (
            start_year or 0,
            start_month or 0,
            start_day or 0
        )
        end_cmp = (
            end_year or 0,
            end_month or 0,
            end_day or 0
        )
        
        if end_cmp < start_cmp:
            raise ValueError("end_date cannot be before the start release_date")
            
        if end_precision == "day":
            last_air_date = f"{end_year}-{str(end_month).zfill(2)}-{str(end_day).zfill(2)}"
        else:
            last_air_precision = {
                "year": end_year,
                "month": end_month,
                "day": None,
                "precision": end_precision
            }
    
    derived_year = start_year
        
    poster_url = None
    if poster_bytes:
        poster_url = await upload_image_from_bytes(poster_bytes, folder="tv_series", public_id=f"{content_id}_poster")
        
    backdrop_url = None
    if backdrop_bytes:
        backdrop_url = await upload_image_from_bytes(backdrop_bytes, folder="tv_series", public_id=f"{content_id}_backdrop")
        
    doc = {
        "_id": content_id,
        "title": title,
        "original_title": original_title,
        "year": derived_year,
        "first_air_date": first_air_date,
        "first_air_precision": first_air_precision,
        "last_air_date": last_air_date,
        "last_air_precision": last_air_precision,
        "total_seasons": total_seasons,
        "total_episodes": total_episodes,
        "episode_runtime_minutes": episode_runtime_minutes,
        "genres": genres,
        "creators": creators,
        "cast": [],
        "plot": plot,
        "language": language,
        "country": country,
        "rating": {"tmdb": None, "tmdb_vote_count": None},
        "images": {
            "poster": poster_url,
            "backdrop": backdrop_url
        },
        "trailer_url": trailer_url,
        "status": status,
        "tagline": tagline,
        "content_type": "tv_series",
        "is_deleted": False,
        "deleted_at": None,
        "needs_release_review": False,
        "source_metadata": {
            "source": "manual",
            "created_by": str(admin_id)
        }
    }
    
    await tv_series_repository.create_tv_series(doc)
    return content_id

async def update_tv_series(
    admin_id: str,
    content_id: str,
    title: str | None = None,
    original_title: str | None = None,
    released: bool | None = None,
    status_value: str | None = None,
    start_day: int | None = None,
    start_month: int | None = None,
    start_year: int | None = None,
    start_precision: str | None = None,
    end_day: int | None = None,
    end_month: int | None = None,
    end_year: int | None = None,
    end_precision: str | None = None,
    clear_end_date: bool = False,
    total_seasons: int | None = None,
    total_episodes: int | None = None,
    episode_runtime_minutes: int | None = None,
    genres: list[str] | None = None,
    creators: list[str] | None = None,
    plot: str | None = None,
    language: list[str] | None = None,
    country: list[str] | None = None,
    tagline: str | None = None,
    trailer_url: str | None = None,
    poster_bytes: bytes | None = None,
    backdrop_bytes: bytes | None = None
):
    updates = {}
    
    if title is not None:
        updates["title"] = title
    if original_title is not None:
        updates["original_title"] = original_title
    if total_seasons is not None:
        updates["total_seasons"] = total_seasons
    if total_episodes is not None:
        updates["total_episodes"] = total_episodes
    if episode_runtime_minutes is not None:
        updates["episode_runtime_minutes"] = episode_runtime_minutes
    if genres is not None:
        updates["genres"] = genres
    if creators is not None:
        updates["creators"] = creators
    if plot is not None:
        updates["plot"] = plot
    if language is not None:
        updates["language"] = language
    if country is not None:
        updates["country"] = country
    if tagline is not None:
        updates["tagline"] = tagline
    if trailer_url is not None:
        updates["trailer_url"] = trailer_url
        
    if released is not None and status_value is not None:
        if released and status_value not in ["Returning Series", "Ended", "Canceled"]:
            raise ValueError("Invalid status for released TV series")
        if not released and status_value not in ["Planned", "In Production", "Pilot"]:
            raise ValueError("Invalid status for unreleased TV series")
        updates["status"] = status_value
        
    if start_precision is not None:
        if released and start_precision != "day":
            raise ValueError("A released TV series must have day precision for its start date.")
            
        start_date_obj = parse_release_date(start_day, start_month, start_year, start_precision)
        if start_precision == "day":
            updates["first_air_date"] = f"{start_year}-{str(start_month).zfill(2)}-{str(start_day).zfill(2)}"
            updates["first_air_precision"] = None
        else:
            updates["first_air_date"] = None
            updates["first_air_precision"] = {
                "year": start_year,
                "month": start_month,
                "day": None,
                "precision": start_precision
            }
        updates["year"] = start_year
        
    # Process end date logic
    if clear_end_date:
        updates["last_air_date"] = None
        updates["last_air_precision"] = None
    elif end_precision is not None:
        end_date_obj = parse_release_date(end_day, end_month, end_year, end_precision)
        
        # Need to fetch existing start date for validation if not updating start date
        current = await tv_series_repository.get_tv_series_by_id(content_id)
        if not current:
            raise ValueError("TV series not found")
            
        curr_s_year = updates.get("year", current.get("year"))
        
        if updates.get("first_air_precision"):
            curr_s_month = updates["first_air_precision"].get("month")
            curr_s_day = updates["first_air_precision"].get("day")
        elif updates.get("first_air_date"):
            # YYYY-MM-DD
            parts = updates["first_air_date"].split("-")
            curr_s_month = int(parts[1]) if len(parts) > 1 else None
            curr_s_day = int(parts[2]) if len(parts) > 2 else None
        else:
            if current.get("first_air_precision"):
                curr_s_month = current["first_air_precision"].get("month")
                curr_s_day = current["first_air_precision"].get("day")
            elif current.get("first_air_date"):
                parts = current["first_air_date"].split("-")
                curr_s_month = int(parts[1]) if len(parts) > 1 else None
                curr_s_day = int(parts[2]) if len(parts) > 2 else None
            else:
                curr_s_month = None
                curr_s_day = None
                
        start_cmp = (
            curr_s_year or 0,
            curr_s_month or 0,
            curr_s_day or 0
        )
        end_cmp = (
            end_year or 0,
            end_month or 0,
            end_day or 0
        )
        
        if end_cmp < start_cmp:
            raise ValueError("end_date cannot be before the start release_date")
            
        if end_precision == "day":
            updates["last_air_date"] = f"{end_year}-{str(end_month).zfill(2)}-{str(end_day).zfill(2)}"
            updates["last_air_precision"] = None
        else:
            updates["last_air_date"] = None
            updates["last_air_precision"] = {
                "year": end_year,
                "month": end_month,
                "day": None,
                "precision": end_precision
            }
        
    if poster_bytes:
        poster_url = await upload_image_from_bytes(poster_bytes, folder="tv_series", public_id=f"{content_id}_poster")
        updates["images.poster"] = poster_url
        
    if backdrop_bytes:
        backdrop_url = await upload_image_from_bytes(backdrop_bytes, folder="tv_series", public_id=f"{content_id}_backdrop")
        updates["images.backdrop"] = backdrop_url
        
    if not updates:
        return True
        
    updates["source_metadata.updated_by"] = str(admin_id)
    updates["source_metadata.updated_at"] = datetime.now(timezone.utc)
    
    # Needs release review needs to be recalculated, for now we set it to False on any explicit admin update
    updates["needs_release_review"] = False
    
    return await tv_series_repository.update_tv_series(content_id, updates)

async def delete_tv_series(content_id: str):
    return await tv_series_repository.soft_delete_tv_series(content_id)
