from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="admin")

    projects: Mapped[list["Project"]] = relationship(back_populates="creator")


class BrandProfile(Base):
    __tablename__ = "brand_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), default="默认品牌")
    description: Mapped[str] = mapped_column(Text, default="")
    style_summary: Mapped[str] = mapped_column(Text, default="")
    recommended_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    materials: Mapped[list["BrandMaterial"]] = relationship(back_populates="brand_profile")
    projects: Mapped[list["Project"]] = relationship(back_populates="brand_profile")


class BrandMaterial(Base):
    __tablename__ = "brand_materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    brand_profile_id: Mapped[int] = mapped_column(ForeignKey("brand_profiles.id"))
    material_type: Mapped[str] = mapped_column(String(32), default="text")
    file_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_text: Mapped[str] = mapped_column(Text, default="")

    brand_profile: Mapped[BrandProfile] = relationship(back_populates="materials")


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    page_type: Mapped[str] = mapped_column(String(32), default="main_image")
    platform: Mapped[str] = mapped_column(String(32), default="taobao")
    product_name: Mapped[str] = mapped_column(String(128), default="")
    brand_profile_id: Mapped[int | None] = mapped_column(ForeignKey("brand_profiles.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="unreviewed")
    latest_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    product_category_id: Mapped[int | None] = mapped_column(ForeignKey("product_categories.id"), nullable=True)

    creator: Mapped[User] = relationship(back_populates="projects")
    brand_profile: Mapped[BrandProfile | None] = relationship(back_populates="projects")
    versions: Mapped[list["Version"]] = relationship(
        back_populates="project",
        foreign_keys="Version.project_id",
        cascade="all, delete-orphan",
        order_by="Version.version_no",
    )
    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class Version(TimestampMixin, Base):
    __tablename__ = "versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    version_no: Mapped[int] = mapped_column(Integer)
    prompt_text: Mapped[str] = mapped_column(Text, default="")
    title_text: Mapped[str] = mapped_column(String(255), default="")
    review_status: Mapped[str] = mapped_column(String(32), default="unreviewed")
    review_comment: Mapped[str] = mapped_column(Text, default="")
    is_final: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_version_id: Mapped[int | None] = mapped_column(ForeignKey("versions.id"), nullable=True)
    input_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    content_type: Mapped[str] = mapped_column(String(32), default="main_image")  # scene_image / detail_module / video / copy

    project: Mapped[Project] = relationship(back_populates="versions", foreign_keys=[project_id])
    parent_version: Mapped[Optional["Version"]] = relationship(remote_side=lambda: Version.id)
    assets: Mapped[list["Asset"]] = relationship(back_populates="version", cascade="all, delete-orphan")
    chat_messages: Mapped[list["ChatMessage"]] = relationship(back_populates="version")


class Asset(TimestampMixin, Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("versions.id"))
    file_path: Mapped[str] = mapped_column(String(255))
    asset_type: Mapped[str] = mapped_column(String(32))
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    version: Mapped[Version] = relationship(back_populates="assets")


class ChatMessage(TimestampMixin, Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    version_id: Mapped[int | None] = mapped_column(ForeignKey("versions.id"), nullable=True)
    thread_id: Mapped[int | None] = mapped_column(ForeignKey("conversation_threads.id"), nullable=True)
    sender_type: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)

    project: Mapped[Project] = relationship(back_populates="chat_messages")
    version: Mapped[Version | None] = relationship(back_populates="chat_messages")
    thread: Mapped["ConversationThread | None"] = relationship(back_populates="messages")


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key_name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    key_value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


# ---------------------------------------------------------------------------
# v0.5 new models
# ---------------------------------------------------------------------------


class ProductCategory(TimestampMixin, Base):
    """Configurable product category tree (e.g. 洗手盆→立柱/台上/挂墙)."""

    __tablename__ = "product_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("product_categories.id"), nullable=True, index=True)
    prompt_template: Mapped[str] = mapped_column(Text, default="")
    scene_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    parent: Mapped[Optional["ProductCategory"]] = relationship(
        remote_side=lambda: ProductCategory.id, backref="children"
    )
    tasks: Mapped[list["Task"]] = relationship(back_populates="product_category")


class Task(TimestampMixin, Base):
    """Top-level workflow container above Project."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    entry_type: Mapped[str] = mapped_column(String(32))  # competitor_link / white_bg_upload / image_scene_video
    current_step: Mapped[str] = mapped_column(String(32), default="input", index=True)  # input / product_select / scene_generate / content_extend / review_finalize
    task_config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    product_category_id: Mapped[int | None] = mapped_column(ForeignKey("product_categories.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)  # active / error / completed / cancelled

    project: Mapped[Project | None] = relationship()
    product_category: Mapped[ProductCategory | None] = relationship(back_populates="tasks")
    candidates: Mapped[list["Candidate"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    crawl_runs: Mapped[list["CrawlRun"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    threads: Mapped[list["ConversationThread"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class CrawlRun(TimestampMixin, Base):
    """Record of a single crawl execution."""

    __tablename__ = "crawl_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    source_url: Mapped[str] = mapped_column(String(1024))
    source_platform: Mapped[str] = mapped_column(String(32), default="unknown")  # 1688 / taobao / other
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending / running / completed / failed
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error_message: Mapped[str] = mapped_column(Text, default="")

    task: Mapped[Task] = relationship(back_populates="crawl_runs")


class Candidate(TimestampMixin, Base):
    """Unified candidate pool for crawled / generated / uploaded images."""

    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(32))  # crawled / generated / uploaded / supplemented
    file_path: Mapped[str] = mapped_column(String(255))
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    task: Mapped[Task] = relationship(back_populates="candidates")


class ConversationThread(TimestampMixin, Base):
    """Segmented conversation within a task.

    P1 fix: bound to task_id + project_id for scope isolation.
    """

    __tablename__ = "conversation_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    thread_type: Mapped[str] = mapped_column(String(32), default="main")  # main / clarify / review

    task: Mapped[Task] = relationship(back_populates="threads")
    messages: Mapped[list[ChatMessage]] = relationship(back_populates="thread")
