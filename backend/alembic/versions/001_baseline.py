"""baseline v0.4.0 - stamp existing schema

Revision ID: 001_baseline
Revises:
Create Date: 2026-03-25

Baseline migration for existing databases. Does not alter any tables;
only stamps the alembic_version so future migrations can run.
"""
from __future__ import annotations

from typing import Sequence, Union

revision: str = "001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing schema created by db_migrations.apply_schema_baseline().
    # This migration only stamps the version.
    pass


def downgrade() -> None:
    pass
