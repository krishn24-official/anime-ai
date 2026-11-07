from app.services.cloudinary_service import upload_image_from_bytes


class CloudinaryImageStorage:
    """ImageStorage backed by Cloudinary.

    Wraps the existing cloudinary_service until that module is migrated here.
    """

    async def upload(self, data: bytes, folder: str) -> str | None:
        return await upload_image_from_bytes(data, folder=folder) or None
