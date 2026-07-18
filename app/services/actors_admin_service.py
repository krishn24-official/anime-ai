import uuid
from datetime import datetime, timezone
from app.repositories import actors_repository
from app.services.cloudinary_service import upload_image_from_bytes
from app.backend.utils.slug import create_slug

async def create_actor(
    admin_id: str,
    name: str,
    birthdate: str | None,
    biography: str | None,
    image_bytes: bytes | None
):
    if not name:
        raise ValueError("Name must be provided")
        
    # Generate unique ID based on name or UUID
    slug = create_slug(name)
    actor_id = f"actor_{slug}"
    
    image_url = None
    if image_bytes:
        image_url = await upload_image_from_bytes(image_bytes, folder="actors", public_id=f"{actor_id}_profile")
        
    doc = {
        "_id": actor_id,
        "name": name,
        "birthdate": birthdate,
        "biography": biography,
        "images": {
            "profile": image_url
        },
        "is_deleted": False,
        "deleted_at": None,
        "source_metadata": {
            "source": "manual",
            "created_by": str(admin_id),
            "created_at": datetime.now(timezone.utc)
        }
    }
    
    await actors_repository.create_actor(doc)
    return actor_id

async def update_actor(
    admin_id: str,
    actor_id: str,
    name: str | None = None,
    birthdate: str | None = None,
    biography: str | None = None,
    image_bytes: bytes | None = None
):
    updates = {}
    
    if name is not None:
        updates["name"] = name
    if birthdate is not None:
        updates["birthdate"] = birthdate
    if biography is not None:
        updates["biography"] = biography
        
    if image_bytes:
        image_url = await upload_image_from_bytes(image_bytes, folder="actors", public_id=f"{actor_id}_profile")
        updates["images.profile"] = image_url
        
    if not updates:
        return True
        
    updates["source_metadata.updated_by"] = str(admin_id)
    updates["source_metadata.updated_at"] = datetime.now(timezone.utc)
    
    return await actors_repository.update_actor(actor_id, updates)

async def delete_actor(actor_id: str):
    return await actors_repository.soft_delete_actor(actor_id)
