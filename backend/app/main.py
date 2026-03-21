from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import auth, brand, projects, settings, upload
from .core.config import settings as app_settings
from .db import init_db

app = FastAPI(title=app_settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth.router, prefix=app_settings.api_prefix)
app.include_router(projects.router, prefix=app_settings.api_prefix)
app.include_router(upload.router, prefix=app_settings.api_prefix)
app.include_router(brand.router, prefix=app_settings.api_prefix)
app.include_router(settings.router, prefix=app_settings.api_prefix)

app.mount("/storage", StaticFiles(directory=app_settings.storage_dir, check_dir=False), name="storage")


def _frontend_index_path() -> Path:
    return app_settings.frontend_dist_dir / "index.html"


def _frontend_is_available() -> bool:
    return app_settings.serve_frontend and _frontend_index_path().exists()


def _resolve_frontend_target(path: str) -> Path:
    if not path:
        return _frontend_index_path()

    relative_path = Path(path)
    candidate = (app_settings.frontend_dist_dir / relative_path).resolve()
    try:
        candidate.relative_to(app_settings.frontend_dist_dir.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc

    if candidate.is_file():
        return candidate
    return _frontend_index_path()


@app.get("/", include_in_schema=False)
def frontend_index() -> FileResponse:
    if not _frontend_is_available():
        raise HTTPException(status_code=404, detail="Frontend build not found")
    return FileResponse(_frontend_index_path())


@app.get("/{full_path:path}", include_in_schema=False)
def frontend_spa(full_path: str) -> FileResponse:
    if full_path.startswith("api/") or full_path == "api":
        raise HTTPException(status_code=404, detail="Not found")
    if full_path.startswith("storage/") or full_path == "storage":
        raise HTTPException(status_code=404, detail="Not found")
    if not _frontend_is_available():
        raise HTTPException(status_code=404, detail="Frontend build not found")
    return FileResponse(_resolve_frontend_target(full_path))
