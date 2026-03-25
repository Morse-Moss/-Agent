from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def _as_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _split_origins(value: str | None) -> list[str]:
    if value is None:
        return ["*"]
    parts = [item.strip() for item in value.split(",")]
    return [item for item in parts if item] or ["*"]


class Settings:
    def __init__(self) -> None:
        backend_dir = Path(__file__).resolve().parents[2]
        project_dir = backend_dir.parent
        env_path = backend_dir / ".env"
        load_dotenv(env_path)

        self.project_dir = project_dir
        self.backend_dir = backend_dir
        self.frontend_dir = project_dir / "frontend"
        self.frontend_dist_dir = Path(os.getenv("APP_FRONTEND_DIST_DIR", str(self.frontend_dir / "dist")))
        self.data_dir = Path(os.getenv("APP_DATA_DIR", str(backend_dir / "data")))
        self.storage_dir = Path(os.getenv("APP_STORAGE_DIR", str(backend_dir / "storage")))
        self.database_url = os.getenv(
            "APP_DATABASE_URL",
            "mysql+pymysql://ecom_agent:ecom_agent@127.0.0.1:3306/ecom_art_agent?charset=utf8mb4",
        )
        self.app_name = os.getenv("APP_NAME", "电商内容Agent")
        self.api_prefix = "/api"
        self.secret_key = os.getenv("APP_SECRET_KEY", "demo-secret-change-me")
        self.token_ttl_hours = int(os.getenv("APP_TOKEN_TTL_HOURS", "12"))
        self.default_admin_username = os.getenv("APP_DEFAULT_ADMIN_USERNAME", "admin")
        self.default_admin_password = os.getenv("APP_DEFAULT_ADMIN_PASSWORD", "admin123")
        self.default_brand_name = os.getenv("APP_DEFAULT_BRAND_NAME", "铝域精选")
        self.default_brand_description = os.getenv(
            "APP_DEFAULT_BRAND_DESCRIPTION",
            "专注广告材料铝材，强调工业品质、稳定供货与支持定制。",
        )
        self.allowed_origins = _split_origins(os.getenv("APP_ALLOWED_ORIGINS"))
        self.serve_frontend = _as_bool(os.getenv("APP_SERVE_FRONTEND"), default=True)

        # v0.5 optional infrastructure
        self.redis_url: str | None = os.getenv("APP_REDIS_URL")  # e.g. redis://127.0.0.1:6379
        self.qdrant_url: str | None = os.getenv("APP_QDRANT_URL")  # e.g. http://127.0.0.1:6333
        self.crawler_enabled = _as_bool(os.getenv("APP_CRAWLER_ENABLED"), default=False)

        # Video provider (optional)
        self.video_provider: str | None = os.getenv("APP_VIDEO_PROVIDER")
        self.video_api_url: str | None = os.getenv("APP_VIDEO_API_URL")
        self.video_model: str | None = os.getenv("APP_VIDEO_MODEL")
        self.video_api_key: str | None = os.getenv("APP_VIDEO_API_KEY")

        # Cutout provider (optional, default: rembg local)
        self.cutout_provider: str = os.getenv("APP_CUTOUT_PROVIDER", "rembg")
        self.cutout_api_url: str | None = os.getenv("APP_CUTOUT_API_URL")
        self.cutout_api_key: str | None = os.getenv("APP_CUTOUT_API_KEY")

    @property
    def is_default_secret(self) -> bool:
        return self.secret_key == "demo-secret-change-me"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


settings = Settings()
