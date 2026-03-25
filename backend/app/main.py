from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import auth, brand, categories, crawl, knowledge, projects, settings, tasks, upload
from .core.config import settings as app_settings
from .db import check_database_connection, init_db
from .schemas import ReadinessResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title=app_settings.app_name, version="0.5.0")

allow_all_origins = app_settings.allowed_origins == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all_origins else app_settings.allowed_origins,
    allow_credentials=not allow_all_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    if app_settings.is_default_secret:
        logger.warning(
            "APP_SECRET_KEY is using the default value. "
            "Set a strong secret via APP_SECRET_KEY env var before deploying to production."
        )
    if app_settings.default_admin_password == "admin123":
        logger.warning(
            "Default admin password is 'admin123'. "
            "Change it via APP_DEFAULT_ADMIN_PASSWORD env var or update after first login."
        )
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", response_model=ReadinessResponse)
def readiness(response: Response) -> ReadinessResponse:
    database_ok = check_database_connection()
    storage_ok = app_settings.storage_dir.exists() and app_settings.storage_dir.is_dir()
    frontend_ok = not app_settings.serve_frontend or _frontend_index_path().exists()
    overall_ok = database_ok and storage_ok and frontend_ok

    if not overall_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="ok" if overall_ok else "degraded",
        database=database_ok,
        storage=storage_ok,
        frontend=frontend_ok,
    )


app.include_router(auth.router, prefix=app_settings.api_prefix)
app.include_router(projects.router, prefix=app_settings.api_prefix)
app.include_router(upload.router, prefix=app_settings.api_prefix)
app.include_router(brand.router, prefix=app_settings.api_prefix)
app.include_router(settings.router, prefix=app_settings.api_prefix)
app.include_router(tasks.router, prefix=app_settings.api_prefix)
app.include_router(crawl.router, prefix=app_settings.api_prefix)
app.include_router(categories.router, prefix=app_settings.api_prefix)
app.include_router(knowledge.router, prefix=app_settings.api_prefix)

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
