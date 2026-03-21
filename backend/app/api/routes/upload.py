from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from ...schemas import UploadImageResponse
from ...services.storage import StorageService
from ..dependencies import get_current_user

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("/image", response_model=UploadImageResponse)
def upload_image(
    image: UploadFile = File(...),
    _current_user=Depends(get_current_user),
) -> UploadImageResponse:
    storage = StorageService()
    result = storage.save_upload(image)
    return UploadImageResponse(**result)
