from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile
from typing import Optional
from app.api.deps import get_current_admin
from app.services import actors_admin_service
from app.services.actors_service import fetch_all_actors

router = APIRouter(
    prefix="/admin/actors",
    tags=["Admin Actors"]
)

@router.get("")
async def list_actors(
    include_deleted: bool = False,
    search: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
    current_admin: dict = Depends(get_current_admin)
):
    return await fetch_all_actors(include_deleted, search, limit, skip)

@router.post("")
async def create_new_actor(
    name: str = Form(...),
    birthdate: Optional[str] = Form(None),
    biography: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_admin: dict = Depends(get_current_admin)
):
    try:
        image_bytes = await image.read() if image else None
        
        content_id = await actors_admin_service.create_actor(
            admin_id=current_admin["_id"],
            name=name,
            birthdate=birthdate,
            biography=biography,
            image_bytes=image_bytes
        )
        return {"status": "ok", "content_id": content_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/{content_id}")
async def update_existing_actor(
    content_id: str,
    name: Optional[str] = Form(None),
    birthdate: Optional[str] = Form(None),
    biography: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_admin: dict = Depends(get_current_admin)
):
    try:
        image_bytes = await image.read() if image else None
        
        await actors_admin_service.update_actor(
            admin_id=current_admin["_id"],
            actor_id=content_id,
            name=name,
            birthdate=birthdate,
            biography=biography,
            image_bytes=image_bytes
        )
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{content_id}")
async def delete_existing_actor(
    content_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    success = await actors_admin_service.delete_actor(content_id)
    if not success:
        raise HTTPException(status_code=404, detail="Actor not found")
    return {"status": "ok"}
