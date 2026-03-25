"""v0.5 models - tasks, categories, candidates, crawl_runs, threads

Revision ID: 002_v05_models
Revises: 001_baseline
Create Date: 2026-03-25
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_v05_models"
down_revision: Union[str, None] = "001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- New tables ---
    op.create_table(
        "product_categories",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("parent_id", sa.Integer, sa.ForeignKey("product_categories.id"), nullable=True),
        sa.Column("prompt_template", sa.Text, server_default=""),
        sa.Column("scene_keywords", sa.JSON, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="1"),
        sa.Column("sort_order", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("entry_type", sa.String(32), nullable=False),
        sa.Column("current_step", sa.String(32), server_default="input"),
        sa.Column("task_config_json", sa.JSON, nullable=True),
        sa.Column("product_category_id", sa.Integer, sa.ForeignKey("product_categories.id"), nullable=True),
        sa.Column("status", sa.String(32), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "crawl_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.Integer, sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("source_url", sa.String(1024), nullable=False),
        sa.Column("source_platform", sa.String(32), server_default="unknown"),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("result_json", sa.JSON, nullable=True),
        sa.Column("error_message", sa.Text, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "candidates",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.Integer, sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("file_path", sa.String(255), nullable=False),
        sa.Column("is_selected", sa.Boolean, server_default="0"),
        sa.Column("metadata_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "conversation_threads",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.Integer, sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("thread_type", sa.String(32), server_default="main"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Alter existing tables: add nullable columns ---
    op.add_column("projects", sa.Column("product_category_id", sa.Integer, sa.ForeignKey("product_categories.id"), nullable=True))
    op.add_column("versions", sa.Column("content_type", sa.String(32), server_default="main_image"))
    op.add_column("assets", sa.Column("metadata_json", sa.JSON, nullable=True))
    op.add_column("chat_messages", sa.Column("thread_id", sa.Integer, sa.ForeignKey("conversation_threads.id"), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_messages", "thread_id")
    op.drop_column("assets", "metadata_json")
    op.drop_column("versions", "content_type")
    op.drop_column("projects", "product_category_id")
    op.drop_table("conversation_threads")
    op.drop_table("candidates")
    op.drop_table("crawl_runs")
    op.drop_table("tasks")
    op.drop_table("product_categories")
