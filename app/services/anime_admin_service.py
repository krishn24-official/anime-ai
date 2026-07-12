from datetime import datetime, timezone
from app.backend.utils.slug import create_slug
from app.repositories import anime_repository
from app.services.cloudinary_service import upload_image_from_bytes
from app.services.release_date_utils import parse_release_date

def derive_season(month: int | None) -> str | None:
    if month is None:
        return None
    if month in (12, 1, 2):
        return "Winter"
    if month in (3, 4, 5):
        return "Spring"
    if month in (6, 7, 8):
        return "Summer"
    if month in (9, 10, 11):
        return "Fall"
    return None


async def create_anime(
    admin_id: str,
    title_english: str | None,
    title_romaji: str | None,
    title_japanese: str | None,
    synonyms: list[str],
    anime_type: str,
    released: bool,
    sub_status: str,
    genres: list[str],
    studios: list[str],
    source: str,
    episodes: int | None,
    duration: int | None,
    day: int | None,
    month: int | None,
    year: int | None,
    precision: str,
    poster_bytes: bytes | None,
    banner_bytes: bytes | None,
    end_day: int | None = None,
    end_month: int | None = None,
    end_year: int | None = None,
    end_precision: str | None = None
):
    title_str = title_english or title_romaji or title_japanese
    if not title_str:
        raise ValueError("At least one title (english, romaji, or japanese) must be provided")
        
    slug = create_slug(title_str)
    content_id = f"anime_{slug}"
    
    existing = await anime_repository.find_anime_by_slug(slug)
    if existing:
        raise ValueError(f"An anime with this title already exists (content_id: {content_id}). Edit the existing entry instead, or use a more specific title.")
        
    status = sub_status if released else "upcoming"
    
    release_date = parse_release_date(day, month, year, precision)
    season = derive_season(month)
    
    end_date = None
    if end_precision:
        end_date = parse_release_date(end_day, end_month, end_year, end_precision)
        
        r_y = release_date["year"]
        r_m = release_date["month"] or 0
        r_d = release_date["day"] or 0
        
        e_y = end_date["year"]
        e_m = end_date["month"] or 0
        e_d = end_date["day"] or 0
        
        if (e_y, e_m, e_d) < (r_y, r_m, r_d):
            raise ValueError("end_date cannot be before the start release_date")
            
    poster_url = None
    if poster_bytes:
        poster_url = await upload_image_from_bytes(poster_bytes, folder="anime", public_id=f"{content_id}_poster")
        
    banner_url = None
    if banner_bytes:
        banner_url = await upload_image_from_bytes(banner_bytes, folder="anime", public_id=f"{content_id}_banner")
        
    doc = {
        "_id": content_id,
        "title": {
            "english": title_english,
            "romaji": title_romaji,
            "japanese": title_japanese
        },
        "synonyms": synonyms,
        "type": anime_type,
        "status": status,
        "genres": genres,
        "studios": studios,
        "season": season,
        "year": year,
        "source": source,
        "total_seasons": 1,
        "total_episodes": episodes,
        "duration_minutes": duration,
        "rating": {"anilist": None},
        "images": {
            "poster": poster_url,
            "banner": banner_url
        },
        "streaming_platforms": [],
        "related_anime_ids": [],
        "manga_id": None,
        "tags": [],
        "is_deleted": False,
        "deleted_at": None,
        "release_date": release_date,
        # NOTE: end_date is optional and was added retroactively.
        # Consumers MUST use .get("end_date") and handle None gracefully, 
        # as ingested documents will not have this field.
        "end_date": end_date,
        "source_metadata": {
            "source": "manual",
            "created_by": str(admin_id)
        }
    }
    
    await anime_repository.create_anime(doc)
    return content_id

async def update_anime(
    admin_id: str,
    content_id: str,
    title_english: str | None = None,
    title_romaji: str | None = None,
    title_japanese: str | None = None,
    synonyms: list[str] | None = None,
    anime_type: str | None = None,
    released: bool | None = None,
    sub_status: str | None = None,
    genres: list[str] | None = None,
    studios: list[str] | None = None,
    source: str | None = None,
    episodes: int | None = None,
    duration: int | None = None,
    day: int | None = None,
    month: int | None = None,
    year: int | None = None,
    precision: str | None = None,
    poster_bytes: bytes | None = None,
    banner_bytes: bytes | None = None,
    end_day: int | None = None,
    end_month: int | None = None,
    end_year: int | None = None,
    end_precision: str | None = None,
    clear_end_date: bool = False
):
    updates = {}
    
    if title_english is not None:
        updates["title.english"] = title_english
    if title_romaji is not None:
        updates["title.romaji"] = title_romaji
    if title_japanese is not None:
        updates["title.japanese"] = title_japanese
        
    if synonyms is not None:
        updates["synonyms"] = synonyms
    if anime_type is not None:
        updates["type"] = anime_type
    if genres is not None:
        updates["genres"] = genres
    if studios is not None:
        updates["studios"] = studios
    if source is not None:
        updates["source"] = source
    if episodes is not None:
        updates["total_episodes"] = episodes
    if duration is not None:
        updates["duration_minutes"] = duration
        
    if released is not None and sub_status is not None:
        updates["status"] = sub_status if released else "upcoming"
        
    if precision is not None:
        release_date = parse_release_date(day, month, year, precision)
        updates["release_date"] = release_date
        updates["season"] = derive_season(month)
        updates["year"] = year
        
    if poster_bytes:
        poster_url = await upload_image_from_bytes(poster_bytes, folder="anime", public_id=f"{content_id}_poster")
        updates["images.poster"] = poster_url
        
    if banner_bytes:
        banner_url = await upload_image_from_bytes(banner_bytes, folder="anime", public_id=f"{content_id}_banner")
        updates["images.banner"] = banner_url
        
    if clear_end_date:
        updates["end_date"] = None
    elif end_precision is not None:
        new_end_date = parse_release_date(end_day, end_month, end_year, end_precision)
        
        # Need to validate against release_date
        # If release_date is being updated in this call, use the new one. Otherwise fetch existing.
        r_date = None
        if "release_date" in updates:
            r_date = updates["release_date"]
        else:
            existing_anime = await anime_repository.find_anime_by_slug(content_id.replace("anime_", ""))
            if existing_anime and existing_anime.get("release_date"):
                r_date = existing_anime["release_date"]
                
        if r_date:
            r_y = r_date["year"]
            r_m = r_date["month"] or 0
            r_d = r_date["day"] or 0
            
            e_y = new_end_date["year"]
            e_m = new_end_date["month"] or 0
            e_d = new_end_date["day"] or 0
            
            if (e_y, e_m, e_d) < (r_y, r_m, r_d):
                raise ValueError("end_date cannot be before the start release_date")
                
        updates["end_date"] = new_end_date
        
    if not updates:
        return True
        
    updates["source_metadata.updated_by"] = str(admin_id)
    updates["source_metadata.updated_at"] = datetime.now(timezone.utc)
    
    return await anime_repository.update_anime(content_id, updates)

async def delete_anime(content_id: str):
    return await anime_repository.soft_delete_anime(content_id)
