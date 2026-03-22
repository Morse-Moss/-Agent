from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.db import create_schema  # noqa: E402
from backend.app.models import (  # noqa: E402
    Asset,
    BrandMaterial,
    BrandProfile,
    ChatMessage,
    Project,
    SystemSetting,
    User,
    Version,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate local SQLite data into a MySQL database.")
    parser.add_argument("--sqlite-url", default="sqlite:///./backend/data/app.db", help="Source SQLite SQLAlchemy URL")
    parser.add_argument("--mysql-url", required=True, help="Target MySQL SQLAlchemy URL")
    parser.add_argument("--clear-target", action="store_true", help="Clear target tables before import")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sqlite_engine = create_engine(args.sqlite_url, future=True)
    mysql_engine = create_engine(args.mysql_url, future=True, pool_pre_ping=True)
    create_schema(mysql_engine)

    SourceSession = sessionmaker(bind=sqlite_engine, expire_on_commit=False, class_=Session)
    TargetSession = sessionmaker(bind=mysql_engine, expire_on_commit=False, class_=Session)

    with SourceSession() as source_session, TargetSession() as target_session:
        if args.clear_target:
            clear_target_tables(target_session)
        elif target_has_data(target_session):
            raise SystemExit("Target MySQL database already contains data. Re-run with --clear-target to overwrite it.")

        transfer_all(source_session, target_session)
        summary = collect_counts(target_session)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def target_has_data(session: Session) -> bool:
    checks = [
        select(User.id),
        select(BrandProfile.id),
        select(Project.id),
        select(Version.id),
        select(Asset.id),
        select(ChatMessage.id),
        select(SystemSetting.id),
    ]
    return any(session.execute(statement.limit(1)).first() for statement in checks)


def clear_target_tables(session: Session) -> None:
    for model in [Asset, ChatMessage, Version, Project, BrandMaterial, BrandProfile, User, SystemSetting]:
        session.query(model).delete()
    session.commit()


def transfer_all(source_session: Session, target_session: Session) -> None:
    copy_rows(source_session, target_session, User)
    copy_rows(source_session, target_session, BrandProfile)
    copy_rows(source_session, target_session, BrandMaterial)
    copy_rows(source_session, target_session, Project)
    copy_rows(source_session, target_session, Version)
    copy_rows(source_session, target_session, Asset)
    copy_rows(source_session, target_session, ChatMessage)
    copy_rows(source_session, target_session, SystemSetting)
    target_session.commit()


def copy_rows(source_session: Session, target_session: Session, model: Any) -> None:
    columns = [column.name for column in model.__table__.columns]
    rows = list(source_session.scalars(select(model).order_by(model.id.asc())))
    for row in rows:
        payload = {column: getattr(row, column) for column in columns}
        target_session.add(model(**payload))
    target_session.flush()


def collect_counts(session: Session) -> dict[str, int]:
    return {
        "users": session.query(User).count(),
        "brand_profiles": session.query(BrandProfile).count(),
        "brand_materials": session.query(BrandMaterial).count(),
        "projects": session.query(Project).count(),
        "versions": session.query(Version).count(),
        "assets": session.query(Asset).count(),
        "chat_messages": session.query(ChatMessage).count(),
        "system_settings": session.query(SystemSetting).count(),
    }


if __name__ == "__main__":
    raise SystemExit(main())
