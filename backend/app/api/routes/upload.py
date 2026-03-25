"""Upload API routes — file upload with security validation."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from ...schemas import UploadImageResponse
from ...services.storage import StorageService
from ..dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])

# Security: allowed MIME types and max file size
_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB


@router.post("/image", response_model=UploadImageResponse)
def upload_image(
    image: UploadFile = File(...),
    _current_user=Depends(get_current_user),
) -> UploadImageResponse:
    # Validate content type
    content_type = (image.content_type or "").lower()
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"File type '{content_type}' not allowed. Accepted: {', '.join(_ALLOWED_CONTENT_TYPES)}",
        )

    # Validate file size (read and check)
    image.file.seek(0, 2)  # seek to end
    file_size = image.file.tell()
    image.file.seek(0)  # reset
    if file_size > _MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({file_size // 1024 // 1024}MB). Max: {_MAX_FILE_SIZE_BYTES // 1024 // 1024}MB",
        )

    # Save file
    storage = StorageService()
    try:
        result = storage.save_upload(image)
    except UnidentifiedImageError:
        raise HTTPException(status_code=422, detail="Invalid image file: cannot be opened as an image")
    except OSError as exc:
        logger.exception("File upload I/O error")
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}")

    return UploadImageResponse(**result)
