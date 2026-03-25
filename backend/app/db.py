from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .core.config import settings
from .core.security import hash_password
from .db_migrations import SCHEMA_BASELINE, apply_schema_baseline
from .models import BrandProfile, ProductCategory, SystemSetting, User
from .text_utils import looks_broken_text

SCHEMA_VERSION = SCHEMA_BASELINE


def _create_engine(database_url: str) -> Engine:
    connect_args: dict[str, object] = {}
    engine_kwargs: dict[str, object] = {"future": True}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    else:
        engine_kwargs["pool_pre_ping"] = True
    return create_engine(database_url, connect_args=connect_args, **engine_kwargs)


engine = _create_engine(settings.database_url)
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


def create_schema(target_engine: Engine | None = None) -> None:
    apply_schema_baseline(target_engine or engine)


def check_database_connection(target_engine: Engine | None = None) -> bool:
    current_engine = target_engine or engine
    try:
        with current_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def init_db() -> None:
    ensure_directories()
    create_schema()
    with SessionLocal() as session:
        _seed_default_user(session)
        _seed_default_brand(session)
        _seed_default_categories(session)
        _store_schema_version(session)
        session.commit()


def _store_schema_version(session: Session) -> None:
    setting = session.scalar(select(SystemSetting).where(SystemSetting.key_name == "APP_SCHEMA_VERSION"))
    if not setting:
        setting = SystemSetting(key_name="APP_SCHEMA_VERSION", key_value=SCHEMA_VERSION)
        session.add(setting)
        return
    setting.key_value = SCHEMA_VERSION


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
    default_style_summary = "品牌整体偏工业高级感，强调材质表现、稳定供货与定制能力。"
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
    return any(looks_broken_text(value) for value in [profile.name, profile.description, profile.style_summary, *keywords])


def _seed_default_categories(session: Session) -> None:
    """Seed bathroom product categories if none exist."""
    existing = session.scalar(select(ProductCategory))
    if existing:
        return

    # Root categories
    washbasin = ProductCategory(
        name="洗手盆",
        prompt_template="一个{sub_type}洗手盆，放置在现代卫浴空间中，{scene_desc}",
        scene_keywords=["卫浴空间", "洗手台", "镜子", "水龙头"],
        sort_order=1,
    )
    bathtub = ProductCategory(
        name="浴缸",
        prompt_template="一个浴缸，放置在宽敞的浴室中，{scene_desc}",
        scene_keywords=["浴室", "地砖", "淋浴", "浴帘"],
        sort_order=2,
    )
    session.add_all([washbasin, bathtub])
    session.flush()

    # Washbasin sub-categories
    sub_types = [
        ("立柱", "立柱式洗手盆，落地安装，{scene_desc}", ["立柱", "落地", "独立式"], 1),
        ("台上", "台上盆，安装在洗手台面上方，{scene_desc}", ["台面", "台上盆", "大理石"], 2),
        ("挂墙", "挂墙式洗手盆，壁挂安装节省空间，{scene_desc}", ["壁挂", "挂墙", "节省空间"], 3),
    ]
    for name, template, keywords, order in sub_types:
        session.add(ProductCategory(
            name=name,
            parent_id=washbasin.id,
            prompt_template=template,
            scene_keywords=keywords,
            sort_order=order,
        ))
