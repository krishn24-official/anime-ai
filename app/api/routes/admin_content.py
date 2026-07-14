from fastapi import APIRouter, Depends, HTTPException, status, Form, File, UploadFile
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from app.api.deps import get_current_admin
import json
from app.services import trending_service
from app.services import anime_admin_service
from app.repositories.anime_repository import list_anime_for_admin
from app.services.content_types import VALID_CONTENT_TYPES

router = APIRouter(
    prefix="/admin",
    tags=["Admin Content"]
)

class SetTrendingRequest(BaseModel):
    content_type: str
    content_id: str
    note: Optional[str] = None
    expires_at: Optional[datetime] = None

@router.get("/trending")
async def get_active_trending(current_admin: dict = Depends(get_current_admin)):
    # Reusing the service method to return the active pinned items
    # (could just return get_trending_content but we might want just raw in future,
    # for now getting the enriched ones is fine for the admin panel)
    return await trending_service.get_trending_content(limit=100)

@router.post("/trending")
async def set_manual_trending(
    content_type: str = Form(...),
    content_id: str = Form(...),
    note: Optional[str] = Form(None),
    expires_at: Optional[datetime] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_admin: dict = Depends(get_current_admin)
):
    if content_type not in VALID_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid content type. Must be one of {VALID_CONTENT_TYPES}"
        )
        
    image_bytes = None
    if image:
        content = await image.read()
        if content:
            image_bytes = content

    success = await trending_service.set_manual_trending(
        content_type=content_type,
        content_id=content_id,
        admin_id=current_admin["_id"],
        note=note,
        expires_at=expires_at,
        image_bytes=image_bytes
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found"
        )
        
    return {"status": "ok"}

@router.delete("/trending/{content_type}/{content_id}")
async def remove_manual_trending(
    content_type: str,
    content_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    await trending_service.remove_manual_trending(content_type, content_id)
    return {"status": "ok"}

# --- Anime Admin ---

@router.get("/anime")
async def list_anime(
    include_deleted: bool = False,
    search: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
    needs_review: bool = False,
    current_admin: dict = Depends(get_current_admin)
):
    return await list_anime_for_admin(include_deleted, search, limit, skip, needs_review)

@router.post("/anime")
async def create_new_anime(
    title_english: Optional[str] = Form(None),
    title_romaji: Optional[str] = Form(None),
    title_japanese: Optional[str] = Form(None),
    synonyms: str = Form("[]"),
    anime_type: str = Form(...),
    released: bool = Form(...),
    sub_status: str = Form(...),
    genres: str = Form("[]"),
    studios: str = Form("[]"),
    source: str = Form(...),
    episodes: Optional[int] = Form(None),
    duration: Optional[int] = Form(None),
    day: Optional[int] = Form(None),
    month: Optional[int] = Form(None),
    year: Optional[int] = Form(None),
    precision: str = Form(...),
    poster: Optional[UploadFile] = File(None),
    banner: Optional[UploadFile] = File(None),
    end_day: Optional[int] = Form(None),
    end_month: Optional[int] = Form(None),
    end_year: Optional[int] = Form(None),
    end_precision: Optional[str] = Form(None),
    current_admin: dict = Depends(get_current_admin)
):
    try:
        synonyms_list = json.loads(synonyms)
        genres_list = json.loads(genres)
        studios_list = json.loads(studios)
        
        poster_bytes = await poster.read() if poster else None
        banner_bytes = await banner.read() if banner else None
        
        content_id = await anime_admin_service.create_anime(
            admin_id=current_admin["_id"],
            title_english=title_english,
            title_romaji=title_romaji,
            title_japanese=title_japanese,
            synonyms=synonyms_list,
            anime_type=anime_type,
            released=released,
            sub_status=sub_status,
            genres=genres_list,
            studios=studios_list,
            source=source,
            episodes=episodes,
            duration=duration,
            day=day,
            month=month,
            year=year,
            precision=precision,
            poster_bytes=poster_bytes,
            banner_bytes=banner_bytes,
            end_day=end_day,
            end_month=end_month,
            end_year=end_year,
            end_precision=end_precision
        )
        return {"status": "ok", "content_id": content_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if "An anime with this title already exists" in str(e):
            raise HTTPException(status_code=409, detail=str(e))
        raise

@router.patch("/anime/{content_id}")
async def update_existing_anime(
    content_id: str,
    title_english: Optional[str] = Form(None),
    title_romaji: Optional[str] = Form(None),
    title_japanese: Optional[str] = Form(None),
    synonyms: Optional[str] = Form(None),
    anime_type: Optional[str] = Form(None),
    released: Optional[bool] = Form(None),
    sub_status: Optional[str] = Form(None),
    genres: Optional[str] = Form(None),
    studios: Optional[str] = Form(None),
    source: Optional[str] = Form(None),
    episodes: Optional[int] = Form(None),
    duration: Optional[int] = Form(None),
    day: Optional[int] = Form(None),
    month: Optional[int] = Form(None),
    year: Optional[int] = Form(None),
    precision: Optional[str] = Form(None),
    poster: Optional[UploadFile] = File(None),
    banner: Optional[UploadFile] = File(None),
    end_day: Optional[int] = Form(None),
    end_month: Optional[int] = Form(None),
    end_year: Optional[int] = Form(None),
    end_precision: Optional[str] = Form(None),
    clear_end_date: bool = Form(False),
    current_admin: dict = Depends(get_current_admin)
):
    try:
        synonyms_list = json.loads(synonyms) if synonyms else None
        genres_list = json.loads(genres) if genres else None
        studios_list = json.loads(studios) if studios else None
        
        poster_bytes = await poster.read() if poster else None
        banner_bytes = await banner.read() if banner else None
        
        await anime_admin_service.update_anime(
            admin_id=current_admin["_id"],
            content_id=content_id,
            title_english=title_english,
            title_romaji=title_romaji,
            title_japanese=title_japanese,
            synonyms=synonyms_list,
            anime_type=anime_type,
            released=released,
            sub_status=sub_status,
            genres=genres_list,
            studios=studios_list,
            source=source,
            episodes=episodes,
            duration=duration,
            day=day,
            month=month,
            year=year,
            precision=precision,
            poster_bytes=poster_bytes,
            banner_bytes=banner_bytes,
            end_day=end_day,
            end_month=end_month,
            end_year=end_year,
            end_precision=end_precision,
            clear_end_date=clear_end_date
        )
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/anime/{content_id}")
async def delete_existing_anime(
    content_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    success = await anime_admin_service.delete_anime(content_id)
    if not success:
        raise HTTPException(status_code=404, detail="Anime not found")
    return {"status": "ok"}

# --- Movies Admin ---

@router.get("/movies")
async def list_movies(
    include_deleted: bool = False,
    search: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
    needs_review: bool = False,
    current_admin: dict = Depends(get_current_admin)
):
    from app.repositories.movie_repository import list_movies_for_admin
    return await list_movies_for_admin(include_deleted, search, limit, skip, needs_review)

@router.post("/movies")
async def create_new_movie(
    title: str = Form(...),
    original_title: Optional[str] = Form(None),
    released: bool = Form(...),
    sub_status: str = Form(...),
    day: Optional[int] = Form(None),
    month: Optional[int] = Form(None),
    year: Optional[int] = Form(None),
    precision: str = Form(...),
    runtime_minutes: Optional[int] = Form(None),
    genres: str = Form("[]"),
    director: str = Form("[]"),
    writers: str = Form("[]"),
    plot: Optional[str] = Form(None),
    language: str = Form("[]"),
    country: str = Form("[]"),
    tagline: Optional[str] = Form(None),
    trailer_url: Optional[str] = Form(None),
    poster: Optional[UploadFile] = File(None),
    backdrop: Optional[UploadFile] = File(None),
    current_admin: dict = Depends(get_current_admin)
):
    from app.services import movie_admin_service
    try:
        genres_list = json.loads(genres)
        director_list = json.loads(director)
        writers_list = json.loads(writers)
        language_list = json.loads(language)
        country_list = json.loads(country)
        
        poster_bytes = await poster.read() if poster else None
        backdrop_bytes = await backdrop.read() if backdrop else None
        
        content_id = await movie_admin_service.create_movie(
            admin_id=current_admin["_id"],
            title=title,
            original_title=original_title,
            released=released,
            sub_status=sub_status,
            day=day,
            month=month,
            year=year,
            precision=precision,
            runtime_minutes=runtime_minutes,
            genres=genres_list,
            director=director_list,
            writers=writers_list,
            plot=plot,
            language=language_list,
            country=country_list,
            tagline=tagline,
            trailer_url=trailer_url,
            poster_bytes=poster_bytes,
            backdrop_bytes=backdrop_bytes
        )
        return {"status": "ok", "content_id": content_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if "already exists" in str(e):
            raise HTTPException(status_code=409, detail=str(e))
        raise

@router.patch("/movies/{content_id}")
async def update_existing_movie(
    content_id: str,
    title: Optional[str] = Form(None),
    original_title: Optional[str] = Form(None),
    released: Optional[bool] = Form(None),
    sub_status: Optional[str] = Form(None),
    day: Optional[int] = Form(None),
    month: Optional[int] = Form(None),
    year: Optional[int] = Form(None),
    precision: Optional[str] = Form(None),
    runtime_minutes: Optional[int] = Form(None),
    genres: Optional[str] = Form(None),
    director: Optional[str] = Form(None),
    writers: Optional[str] = Form(None),
    plot: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
    country: Optional[str] = Form(None),
    tagline: Optional[str] = Form(None),
    trailer_url: Optional[str] = Form(None),
    poster: Optional[UploadFile] = File(None),
    backdrop: Optional[UploadFile] = File(None),
    current_admin: dict = Depends(get_current_admin)
):
    from app.services import movie_admin_service
    try:
        genres_list = json.loads(genres) if genres else None
        director_list = json.loads(director) if director else None
        writers_list = json.loads(writers) if writers else None
        language_list = json.loads(language) if language else None
        country_list = json.loads(country) if country else None
        
        poster_bytes = await poster.read() if poster else None
        backdrop_bytes = await backdrop.read() if backdrop else None
        
        await movie_admin_service.update_movie(
            admin_id=current_admin["_id"],
            content_id=content_id,
            title=title,
            original_title=original_title,
            released=released,
            sub_status=sub_status,
            day=day,
            month=month,
            year=year,
            precision=precision,
            runtime_minutes=runtime_minutes,
            genres=genres_list,
            director=director_list,
            writers=writers_list,
            plot=plot,
            language=language_list,
            country=country_list,
            tagline=tagline,
            trailer_url=trailer_url,
            poster_bytes=poster_bytes,
            backdrop_bytes=backdrop_bytes
        )
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/movies/{content_id}")
async def delete_existing_movie(
    content_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    from app.services import movie_admin_service
    success = await movie_admin_service.delete_movie(content_id)
    if not success:
        raise HTTPException(status_code=404, detail="Movie not found")
    return {"status": "ok"}

# --- TV Series Admin ---

@router.get("/tv-series")
async def list_tv_series(
    include_deleted: bool = False,
    search: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
    needs_review: bool = False,
    current_admin: dict = Depends(get_current_admin)
):
    from app.repositories.tv_series_repository import list_tv_series_for_admin
    return await list_tv_series_for_admin(include_deleted, search, limit, skip, needs_review)

@router.post("/tv-series")
async def create_new_tv_series(
    title: str = Form(...),
    original_title: Optional[str] = Form(None),
    released: bool = Form(...),
    status_value: str = Form(...),
    start_day: Optional[int] = Form(None),
    start_month: Optional[int] = Form(None),
    start_year: Optional[int] = Form(None),
    start_precision: str = Form(...),
    end_day: Optional[int] = Form(None),
    end_month: Optional[int] = Form(None),
    end_year: Optional[int] = Form(None),
    end_precision: Optional[str] = Form(None),
    total_seasons: Optional[int] = Form(None),
    total_episodes: Optional[int] = Form(None),
    episode_runtime_minutes: Optional[int] = Form(None),
    genres: str = Form("[]"),
    creators: str = Form("[]"),
    plot: Optional[str] = Form(None),
    language: str = Form("[]"),
    country: str = Form("[]"),
    tagline: Optional[str] = Form(None),
    trailer_url: Optional[str] = Form(None),
    poster: Optional[UploadFile] = File(None),
    backdrop: Optional[UploadFile] = File(None),
    current_admin: dict = Depends(get_current_admin)
):
    try:
        from app.services.tv_series_admin_service import create_tv_series
        genres_list = json.loads(genres)
        creators_list = json.loads(creators)
        language_list = json.loads(language)
        country_list = json.loads(country)
        
        poster_bytes = await poster.read() if poster else None
        backdrop_bytes = await backdrop.read() if backdrop else None
        
        content_id = await create_tv_series(
            admin_id=current_admin["_id"],
            title=title,
            original_title=original_title,
            released=released,
            status_value=status_value,
            start_day=start_day,
            start_month=start_month,
            start_year=start_year,
            start_precision=start_precision,
            end_day=end_day,
            end_month=end_month,
            end_year=end_year,
            end_precision=end_precision,
            total_seasons=total_seasons,
            total_episodes=total_episodes,
            episode_runtime_minutes=episode_runtime_minutes,
            genres=genres_list,
            creators=creators_list,
            plot=plot,
            language=language_list,
            country=country_list,
            tagline=tagline,
            trailer_url=trailer_url,
            poster_bytes=poster_bytes,
            backdrop_bytes=backdrop_bytes
        )
        return {"status": "ok", "content_id": content_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if "already exists" in str(e):
            raise HTTPException(status_code=409, detail=str(e))
        raise

@router.patch("/tv-series/{content_id}")
async def update_existing_tv_series(
    content_id: str,
    title: Optional[str] = Form(None),
    original_title: Optional[str] = Form(None),
    released: Optional[bool] = Form(None),
    status_value: Optional[str] = Form(None),
    start_day: Optional[int] = Form(None),
    start_month: Optional[int] = Form(None),
    start_year: Optional[int] = Form(None),
    start_precision: Optional[str] = Form(None),
    end_day: Optional[int] = Form(None),
    end_month: Optional[int] = Form(None),
    end_year: Optional[int] = Form(None),
    end_precision: Optional[str] = Form(None),
    clear_end_date: bool = Form(False),
    total_seasons: Optional[int] = Form(None),
    total_episodes: Optional[int] = Form(None),
    episode_runtime_minutes: Optional[int] = Form(None),
    genres: Optional[str] = Form(None),
    creators: Optional[str] = Form(None),
    plot: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
    country: Optional[str] = Form(None),
    tagline: Optional[str] = Form(None),
    trailer_url: Optional[str] = Form(None),
    poster: Optional[UploadFile] = File(None),
    backdrop: Optional[UploadFile] = File(None),
    current_admin: dict = Depends(get_current_admin)
):
    try:
        from app.services.tv_series_admin_service import update_tv_series
        genres_list = json.loads(genres) if genres else None
        creators_list = json.loads(creators) if creators else None
        language_list = json.loads(language) if language else None
        country_list = json.loads(country) if country else None
        
        poster_bytes = await poster.read() if poster else None
        backdrop_bytes = await backdrop.read() if backdrop else None
        
        await update_tv_series(
            admin_id=current_admin["_id"],
            content_id=content_id,
            title=title,
            original_title=original_title,
            released=released,
            status_value=status_value,
            start_day=start_day,
            start_month=start_month,
            start_year=start_year,
            start_precision=start_precision,
            end_day=end_day,
            end_month=end_month,
            end_year=end_year,
            end_precision=end_precision,
            clear_end_date=clear_end_date,
            total_seasons=total_seasons,
            total_episodes=total_episodes,
            episode_runtime_minutes=episode_runtime_minutes,
            genres=genres_list,
            creators=creators_list,
            plot=plot,
            language=language_list,
            country=country_list,
            tagline=tagline,
            trailer_url=trailer_url,
            poster_bytes=poster_bytes,
            backdrop_bytes=backdrop_bytes
        )
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/tv-series/{content_id}")
async def delete_existing_tv_series(
    content_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    from app.services.tv_series_admin_service import delete_tv_series
    success = await delete_tv_series(content_id)
    if not success:
        raise HTTPException(status_code=404, detail="TV Series not found")
    return {"status": "ok"}

# --- Episodes Admin ---

@router.get("/episodes")
async def list_episodes(
    parent_id: str,
    parent_type: str,
    include_deleted: bool = False,
    current_admin: dict = Depends(get_current_admin)
):
    from app.repositories.episode_repository import list_episodes_for_admin
    return await list_episodes_for_admin(parent_id, parent_type, include_deleted)

class CreateEpisodeRequest(BaseModel):
    parent_type: str
    parent_content_id: str
    episode_number: int
    title: Optional[str] = None
    release_date: Optional[str] = None
    director: Optional[str] = None
    arc: Optional[str] = None
    is_filler: bool = False
    canon_type: Optional[str] = None
    summary: Optional[str] = None

@router.post("/episodes")
async def create_new_episode(
    req: CreateEpisodeRequest,
    current_admin: dict = Depends(get_current_admin)
):
    from app.services.episode_admin_service import create_episode
    try:
        return await create_episode(
            admin_id=str(current_admin["_id"]),
            parent_type=req.parent_type,
            parent_content_id=req.parent_content_id,
            episode_number=req.episode_number,
            title=req.title,
            release_date=req.release_date,
            director=req.director,
            arc=req.arc,
            is_filler=req.is_filler,
            canon_type=req.canon_type,
            summary=req.summary
        )
    except ValueError as e:
        if "already exists" in str(e):
            raise HTTPException(status_code=409, detail=str(e))
        elif "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))

class UpdateEpisodeRequest(BaseModel):
    title: Optional[str] = None
    release_date: Optional[str] = None
    director: Optional[str] = None
    arc: Optional[str] = None
    is_filler: Optional[bool] = None
    canon_type: Optional[str] = None
    summary: Optional[str] = None

@router.patch("/episodes/{content_id}")
async def update_existing_episode(
    content_id: str,
    req: UpdateEpisodeRequest,
    current_admin: dict = Depends(get_current_admin)
):
    from app.services.episode_admin_service import update_episode
    try:
        success = await update_episode(
            content_id=content_id,
            title=req.title,
            release_date=req.release_date,
            director=req.director,
            arc=req.arc,
            is_filler=req.is_filler,
            canon_type=req.canon_type,
            summary=req.summary
        )
        if not success:
            raise HTTPException(status_code=404, detail="Episode not found")
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/episodes/{content_id}")
async def delete_existing_episode(
    content_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    from app.services.episode_admin_service import delete_episode
    success = await delete_episode(content_id)
    if not success:
        raise HTTPException(status_code=404, detail="Episode not found")
    return {"status": "ok"}


# --- Chapters Admin ---

@router.get("/chapters")
async def list_chapters(
    manga_id: str,
    include_deleted: bool = False,
    current_admin: dict = Depends(get_current_admin)
):
    from app.repositories.chapter_repository import list_chapters_for_admin
    return await list_chapters_for_admin(manga_id, include_deleted)

class CreateChapterRequest(BaseModel):
    manga_id: str
    chapter_number: int
    release_date: Optional[str] = None
    summary: Optional[str] = None

@router.post("/chapters")
async def create_new_chapter(
    req: CreateChapterRequest,
    current_admin: dict = Depends(get_current_admin)
):
    from app.services.chapter_admin_service import create_chapter
    try:
        return await create_chapter(
            admin_id=str(current_admin["_id"]),
            manga_id=req.manga_id,
            chapter_number=req.chapter_number,
            release_date=req.release_date,
            summary=req.summary
        )
    except ValueError as e:
        if "already exists" in str(e):
            raise HTTPException(status_code=409, detail=str(e))
        elif "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))

class UpdateChapterRequest(BaseModel):
    release_date: Optional[str] = None
    summary: Optional[str] = None

@router.patch("/chapters/{content_id}")
async def update_existing_chapter(
    content_id: str,
    req: UpdateChapterRequest,
    current_admin: dict = Depends(get_current_admin)
):
    from app.services.chapter_admin_service import update_chapter
    try:
        success = await update_chapter(
            content_id=content_id,
            release_date=req.release_date,
            summary=req.summary
        )
        if not success:
            raise HTTPException(status_code=404, detail="Chapter not found")
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/chapters/{content_id}")
async def delete_existing_chapter(
    content_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    from app.services.chapter_admin_service import delete_chapter
    success = await delete_chapter(content_id)
    if not success:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return {"status": "ok"}

# --- Relationships Admin ---

@router.get("/relationships/search-entities")
async def get_relationship_entities(
    q: str,
    types: Optional[str] = None,
    limit: int = 10,
    current_admin: dict = Depends(get_current_admin)
):
    from app.repositories.relationship_repository import search_relationship_entities
    if not q or len(q) < 2:
        return []
        
    types_list = [t.strip() for t in types.split(",")] if types else None
    return await search_relationship_entities(q, limit, types_list)

@router.get("/relationships/check")
async def check_relationship_duplicate(
    source_id: str,
    target_id: str,
    relationship: str,
    current_admin: dict = Depends(get_current_admin)
):
    from app.services.relationship_admin_service import check_relationship_exists
    existing = await check_relationship_exists(source_id, target_id, relationship)
    if existing:
        return {"exists": True, "context": existing.get("context", "")}
    return {"exists": False}

class CreateRelationshipRequest(BaseModel):
    source_id: str
    target_id: str
    relationship: str
    type: Optional[str] = None
    context: Optional[str] = None
    inverse_relationship: Optional[str] = None
    overwrite: bool = False

@router.post("/relationships")
async def create_new_relationship(
    req: CreateRelationshipRequest,
    current_admin: dict = Depends(get_current_admin)
):
    from app.services.relationship_admin_service import create_relationship
    try:
        result = await create_relationship(
            admin_id=str(current_admin["_id"]),
            source_id=req.source_id,
            target_id=req.target_id,
            relationship=req.relationship,
            rel_type=req.type,
            context=req.context,
            explicit_inverse=req.inverse_relationship,
            overwrite=req.overwrite
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/relationships/types")
async def get_relationship_types(current_admin: dict = Depends(get_current_admin)):
    from app.backend.constants.anime_enums import RELATIONSHIP_TYPES
    return RELATIONSHIP_TYPES

@router.get("/relationships/common-words")
async def get_relationship_common_words(current_admin: dict = Depends(get_current_admin)):
    from app.backend.constants.anime_enums import RELATIONSHIP_WORDS
    return RELATIONSHIP_WORDS

# --- Characters Admin ---

@router.get("/characters")
async def list_characters(
    search: str = None,
    include_deleted: bool = False,
    limit: int = 20,
    skip: int = 0,
    current_admin: dict = Depends(get_current_admin)
):
    from app.repositories.character_admin_repository import list_characters_for_admin
    items, total = await list_characters_for_admin(include_deleted, search, limit, skip)
    return {"items": items, "total": total}

@router.post("/characters")
async def create_character_admin(
    name: str = Form(...),
    native_name: str = Form(None),
    birth_day: int = Form(None),
    birth_month: int = Form(None),
    height: str = Form(None),
    hair_color: str = Form(None),
    has_hair: bool = Form(None),
    description: str = Form(None),
    anime_ids: str = Form("[]"),
    manga_ids: str = Form("[]"),
    affiliations: str = Form("[]"),
    abilities: str = Form("[]"),
    forms: str = Form("[]"),
    status: str = Form("unknown"),
    species: str = Form("unknown"),
    gender: str = Form(None),
    role: str = Form("unknown"),
    tags: str = Form("[]"),
    profile_image: UploadFile = File(None),
    banner_image: UploadFile = File(None),
    current_admin: dict = Depends(get_current_admin)
):
    from app.services import character_admin_service
    
    try:
        a_ids = json.loads(anime_ids)
        m_ids = json.loads(manga_ids)
        affil = json.loads(affiliations)
        abils = json.loads(abilities)
        frms = json.loads(forms)
        tgs = json.loads(tags)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON array format")

    prof_bytes = await profile_image.read() if profile_image else None
    ban_bytes = await banner_image.read() if banner_image else None

    try:
        content_id = await character_admin_service.create_character(
            admin_id=current_admin["_id"],
            name=name,
            native_name=native_name,
            birth_day=birth_day,
            birth_month=birth_month,
            height=height,
            hair_color=hair_color,
            has_hair=has_hair,
            description=description,
            anime_ids=a_ids,
            manga_ids=m_ids,
            affiliations=affil,
            abilities=abils,
            forms=frms,
            status=status,
            species=species,
            gender=gender,
            role=role,
            tags=tgs,
            profile_bytes=prof_bytes,
            banner_bytes=ban_bytes
        )
        return {"status": "ok", "content_id": content_id}
    except ValueError as e:
        if "already exists" in str(e).lower():
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/characters/{content_id}")
async def update_character_admin(
    content_id: str,
    name: str = Form(None),
    native_name: str = Form(None),
    birth_day: int = Form(None),
    birth_month: int = Form(None),
    height: str = Form(None),
    hair_color: str = Form(None),
    has_hair: bool = Form(None),
    description: str = Form(None),
    anime_ids: str = Form(None),
    manga_ids: str = Form(None),
    affiliations: str = Form(None),
    abilities: str = Form(None),
    forms: str = Form(None),
    status: str = Form(None),
    species: str = Form(None),
    gender: str = Form(None),
    role: str = Form(None),
    tags: str = Form(None),
    profile_image: UploadFile = File(None),
    banner_image: UploadFile = File(None),
    current_admin: dict = Depends(get_current_admin)
):
    from app.services import character_admin_service
    
    try:
        a_ids = json.loads(anime_ids) if anime_ids else None
        m_ids = json.loads(manga_ids) if manga_ids else None
        affil = json.loads(affiliations) if affiliations else None
        abils = json.loads(abilities) if abilities else None
        frms = json.loads(forms) if forms else None
        tgs = json.loads(tags) if tags else None
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON array format")

    prof_bytes = await profile_image.read() if profile_image else None
    ban_bytes = await banner_image.read() if banner_image else None

    try:
        await character_admin_service.update_character(
            admin_id=current_admin["_id"],
            content_id=content_id,
            name=name,
            native_name=native_name,
            birth_day=birth_day,
            birth_month=birth_month,
            height=height,
            hair_color=hair_color,
            has_hair=has_hair,
            description=description,
            anime_ids=a_ids,
            manga_ids=m_ids,
            affiliations=affil,
            abilities=abils,
            forms=frms,
            status=status,
            species=species,
            gender=gender,
            role=role,
            tags=tgs,
            profile_bytes=prof_bytes,
            banner_bytes=ban_bytes
        )
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/characters/{content_id}")
async def delete_character_admin(
    content_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    from app.services import character_admin_service
    try:
        await character_admin_service.delete_character(content_id)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
