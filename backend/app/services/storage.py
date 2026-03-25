from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image

from ..core.config import settings


class StorageService:
    def __init__(self) -> None:
        self.root = Path(settings.storage_dir)
        self.uploads_dir = self.root / "uploads"
        self.processed_dir = self.root / "processed"
        self.exports_dir = self.root / "exports"
        self.ensure_directories()

    def ensure_directories(self) -> None:
        for directory in (self.root, self.uploads_dir, self.processed_dir, self.exports_dir):
            directory.mkdir(parents=True, exist_ok=True)

    def save_upload(self, upload: UploadFile) -> dict[str, int | str | None]:
        suffix = Path(upload.filename or "upload.png").suffix or ".png"
        file_name = f"{uuid4().hex}{suffix}"
        target = self.uploads_dir / file_name
        with target.open("wb") as file_handle:
            shutil.copyfileobj(upload.file, file_handle)
        width, height = self.get_image_dimensions(target)
        return {
            "file_path": self.to_relative_path(target),
            "width": width,
            "height": height,
        }

    def save_image(self, image: Image.Image, bucket: str, suffix: str = ".png") -> dict[str, int | str]:
        base_dir = {
            "processed": self.processed_dir,
            "exports": self.exports_dir,
            "uploads": self.uploads_dir,
        }.get(bucket, self.processed_dir)
        file_name = f"{uuid4().hex}{suffix}"
        target = base_dir / file_name
        image.save(target)
        width, height = image.size
        return {
            "file_path": self.to_relative_path(target),
            "width": width,
            "height": height,
        }

    def absolute_path(self, relative_path: str) -> Path:
        resolved = (self.root / relative_path).resolve()
        # Path traversal protection: ensure resolved path stays within storage root
        try:
            resolved.relative_to(self.root.resolve())
        except ValueError:
            raise ValueError(f"Path traversal detected: {relative_path}")
        return resolved

    def to_relative_path(self, absolute_path: Path) -> str:
        return absolute_path.relative_to(self.root).as_posix()

    def get_image_dimensions(self, path: str | Path) -> tuple[int | None, int | None]:
        real_path = Path(path)
        if not real_path.is_absolute():
            real_path = self.absolute_path(str(path))
        with Image.open(real_path) as image:
            return image.size
