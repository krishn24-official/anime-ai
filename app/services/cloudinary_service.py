import asyncio
import cloudinary
import cloudinary.uploader

from app.config import (
    CLOUDINARY_CLOUD_NAME,
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET,
)

# Configure once on import
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True,
)


def _is_configured() -> bool:
    return all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET])


async def upload_image(
    source: str,
    folder: str = "entertainment_hub",
    public_id: str | None = None,
) -> str | None:
    """
    Upload an image to Cloudinary and return the secure URL.

    source    -- a local file path, a URL, or a base64 data URI
    folder    -- Cloudinary folder (e.g. 'characters', 'movies', 'posters')
    public_id -- optional stable ID (e.g. 'anime_naruto_poster');
                 if not set Cloudinary auto-generates one.

    Returns the secure HTTPS URL, or None on failure.
    """

    if not _is_configured():
        print("[cloudinary] not configured — set CLOUDINARY_CLOUD_NAME, API_KEY, API_SECRET in .env")
        return None

    try:
        def _upload():
            return cloudinary.uploader.upload(
                source,
                folder=folder,
                public_id=public_id,
                overwrite=True,
                resource_type="image",
            )
        result = await asyncio.to_thread(_upload)
        return result.get("secure_url")

    except Exception as e:
        print(f"[cloudinary] upload error: {e}")
        return None


async def upload_image_from_url(
    url: str,
    folder: str = "entertainment_hub",
    public_id: str | None = None,
) -> str | None:
    """Upload from a remote URL (e.g. an OMDb poster URL) — Cloudinary
    fetches it server-side, so no ISP block issues."""
    return await upload_image(url, folder=folder, public_id=public_id)


async def upload_image_from_bytes(
    data: bytes,
    folder: str = "entertainment_hub",
    public_id: str | None = None,
) -> str | None:
    """Upload raw image bytes (e.g. from a file upload in the API)."""
    import io
    return await upload_image(
        io.BytesIO(data),
        folder=folder,
        public_id=public_id,
    )