from datetime import datetime, timezone
from app.backend.utils.slug import create_slug
from app.repositories import movie_repository
from app.services.cloudinary_service import upload_image_from_bytes
from app.services.release_date_utils import parse_release_date

async def create_movie(
    admin_id: str,
    title: str,
    original_title: str | None,
    released: bool,
    sub_status: str,
    day: int | None,
    month: int | None,
    year: int | None,
    precision: str,
    runtime_minutes: int | None,
    genres: list[str],
    director: list[str],
    writers: list[str],
    producers: list[str],
    production_house: list[str],
    actors: list[str],
    plot: str | None,
    language: list[str],
    country: list[str],
    tagline: str | None,
    trailers: list[dict],
    poster_bytes: bytes | None,
    backdrop_bytes: bytes | None
):
    if not title:
        raise ValueError("Title must be provided")
        
    slug = create_slug(title)
    content_id = f"movie_{slug}"
    
    existing = await movie_repository.find_movie_by_slug(slug)
    if existing:
        raise ValueError(f"A movie with this title already exists (content_id: {content_id}). Edit the existing entry instead, or use a more specific title.")
        
    status = "Released" if released else sub_status
    
    release_date_obj = parse_release_date(day, month, year, precision)
    release_date = None
    release_precision = None
    
    if released and precision != "day":
        raise ValueError("A released movie must have day precision for its release date.")
        
    if precision == "day":
        # Format as YYYY-MM-DD
        release_date = f"{year}-{str(month).zfill(2)}-{str(day).zfill(2)}"
    else:
        release_precision = {
            "year": year,
            "month": month,
            "day": None,
            "precision": precision
        }
    
    derived_year = year
        
    poster_url = None
    if poster_bytes:
        poster_url = await upload_image_from_bytes(poster_bytes, folder="movies", public_id=f"{content_id}_poster")
        
    backdrop_url = None
    if backdrop_bytes:
        backdrop_url = await upload_image_from_bytes(backdrop_bytes, folder="movies", public_id=f"{content_id}_backdrop")
        
    doc = {
        "_id": content_id,
        "title": title,
        "original_title": original_title,
        "year": derived_year,
        "release_date": release_date,
        "release_precision": release_precision,
        "runtime_minutes": runtime_minutes,
        "genres": genres,
        "director": director,
        "writers": writers,
        "producers": producers,
        "production_house": production_house,
        "actors": actors,
        "cast": [],
        "plot": plot,
        "language": language,
        "country": country,
        "rating": {"tmdb": None, "tmdb_vote_count": None},
        "images": {
            "poster": poster_url,
            "backdrop": backdrop_url
        },
        "trailers": trailers,
        "status": status,
        "tagline": tagline,
        "budget": None,
        "revenue": None,
        "content_type": "movie",
        "is_deleted": False,
        "deleted_at": None,
        "needs_release_review": False,
        "source_metadata": {
            "source": "manual",
            "created_by": str(admin_id)
        }
    }
    
    await movie_repository.create_movie(doc)
    return content_id

async def update_movie(
    admin_id: str,
    content_id: str,
    title: str | None = None,
    original_title: str | None = None,
    released: bool | None = None,
    sub_status: str | None = None,
    day: int | None = None,
    month: int | None = None,
    year: int | None = None,
    precision: str | None = None,
    runtime_minutes: int | None = None,
    genres: list[str] | None = None,
    director: list[str] | None = None,
    writers: list[str] | None = None,
    producers: list[str] | None = None,
    production_house: list[str] | None = None,
    actors: list[str] | None = None,
    plot: str | None = None,
    language: list[str] | None = None,
    country: list[str] | None = None,
    tagline: str | None = None,
    trailers: list[dict] | None = None,
    poster_bytes: bytes | None = None,
    backdrop_bytes: bytes | None = None
):
    updates = {}
    
    if title is not None:
        updates["title"] = title
    if original_title is not None:
        updates["original_title"] = original_title
    if runtime_minutes is not None:
        updates["runtime_minutes"] = runtime_minutes
    if genres is not None:
        updates["genres"] = genres
    if director is not None:
        updates["director"] = director
    if writers is not None:
        updates["writers"] = writers
    if producers is not None:
        updates["producers"] = producers
    if production_house is not None:
        updates["production_house"] = production_house
    if actors is not None:
        updates["actors"] = actors
    if plot is not None:
        updates["plot"] = plot
    if language is not None:
        updates["language"] = language
    if country is not None:
        updates["country"] = country
    if tagline is not None:
        updates["tagline"] = tagline
    if trailers is not None:
        updates["trailers"] = trailers
        
    if released is not None and sub_status is not None:
        updates["status"] = "Released" if released else sub_status
        
    if precision is not None:
        if released and precision != "day":
            raise ValueError("A released movie must have day precision for its release date.")
            
        release_date_obj = parse_release_date(day, month, year, precision)
        if precision == "day":
            updates["release_date"] = f"{year}-{str(month).zfill(2)}-{str(day).zfill(2)}"
            updates["release_precision"] = None
        else:
            updates["release_date"] = None
            updates["release_precision"] = {
                "year": year,
                "month": month,
                "day": None,
                "precision": precision
            }
        updates["year"] = year
        
    if poster_bytes:
        poster_url = await upload_image_from_bytes(poster_bytes, folder="movies", public_id=f"{content_id}_poster")
        updates["images.poster"] = poster_url
        
    if backdrop_bytes:
        backdrop_url = await upload_image_from_bytes(backdrop_bytes, folder="movies", public_id=f"{content_id}_backdrop")
        updates["images.backdrop"] = backdrop_url
        
    if not updates:
        return True
        
    updates["source_metadata.updated_by"] = str(admin_id)
    updates["source_metadata.updated_at"] = datetime.now(timezone.utc)
    
    # Automatically clear the review flag if admin is updating it
    updates["needs_release_review"] = False
    
    return await movie_repository.update_movie(content_id, updates)

async def delete_movie(content_id: str):
    return await movie_repository.soft_delete_movie(content_id)
