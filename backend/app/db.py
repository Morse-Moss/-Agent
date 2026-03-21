from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from .core.config import settings
from .core.security import hash_password
from .models import Base, BrandProfile, User


def _create_engine():
    connect_args: dict[str, object] = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(settings.database_url, future=True, connect_args=connect_args)


engine = _create_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def ensure_directories() -> None:
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.storage_dir).mkdir(parents=True, exist_ok=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    ensure_directories()
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        _seed_default_user(session)
        _seed_default_brand(session)
        session.commit()


def _seed_default_user(session: Session) -> None:
    existing = session.scalar(select(User).where(User.username == settings.default_admin_username))
    if existing:
        return
    session.add(
        User(
            username=settings.default_admin_username,
            password_hash=hash_password(settings.default_admin_password),
            role="admin",
        )
    )


def _seed_default_brand(session: Session) -> None:
    default_style_summary = "工业感、简洁排版、突出材质纹理和定制能力。"
    default_keywords = ["金属质感", "工业简洁", "耐腐蚀", "高强度", "支持定制"]

    existing = session.scalar(select(BrandProfile))
    if existing:
        if _brand_profile_needs_repair(existing):
            existing.name = settings.default_brand_name
            existing.description = settings.default_brand_description
            existing.style_summary = default_style_summary
            existing.recommended_keywords = default_keywords
        return

    session.add(
        BrandProfile(
            name=settings.default_brand_name,
            description=settings.default_brand_description,
            style_summary=default_style_summary,
            recommended_keywords=default_keywords,
        )
    )


def _brand_profile_needs_repair(profile: BrandProfile) -> bool:
    keywords = profile.recommended_keywords or []
    return any(_looks_broken_text(value) for value in [profile.name, profile.description, profile.style_summary, *keywords])


def _looks_broken_text(value: str | None) -> bool:
    if value is None:
        return True

    text = str(value).strip()
    if not text:
        return True
    if text.count("?") >= 2:
        return True
    if "\ufffd" in text:
        return True

    suspicious_tokens = ("锛", "銆", "鈥", "锟", "鏄", "鐗", "鍝", "浣", "璇", "缁", "姝")
    return sum(token in text for token in suspicious_tokens) >= 2
