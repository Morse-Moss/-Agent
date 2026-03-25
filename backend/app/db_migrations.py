from __future__ import annotations

from sqlalchemy.engine import Engine

from .models import Base

SCHEMA_BASELINE = "0.5.0"


def apply_schema_baseline(engine: Engine) -> None:
    Base.metadata.create_all(bind=engine)
