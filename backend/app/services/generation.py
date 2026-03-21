from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..core.config import settings
from ..models import Asset, BrandProfile, ChatMessage, Project, User, Version
from ..schemas import GenerationResult, ProjectDetail, ProjectListItem
from .image_pipeline import ImagePipeline
from .model_gateway import DemoBrandContext, ModelGateway

PREVIEWABLE_ASSET_TYPES = {"final_export", "composite", "background", "cutout", "source"}


class ProjectService:
    def __init__(
        self,
        db: Session,
        *,
        gateway: ModelGateway,
        image_pipeline: ImagePipeline,
    ) -> None:
        self.db = db
        self.gateway = gateway
        self.image_pipeline = image_pipeline

    def list_projects(self, current_user: User, status: str | None = None) -> list[ProjectListItem]:
        statement = (
            select(Project)
            .order_by(Project.created_at.desc())
            .options(selectinload(Project.versions).selectinload(Version.assets))
        )
        if current_user.role != "admin":
            statement = statement.where(Project.created_by == current_user.id)

        projects = list(self.db.scalars(statement))
        result: list[ProjectListItem] = []
        for project in projects:
            self._refresh_project_status(project)
            if status and project.status != status:
                continue
            result.append(self._build_project_list_item(project))

        self.db.commit()
        return result

    def create_project(self, payload: dict[str, Any], current_user: User) -> ProjectDetail:
        brand = self._get_brand_profile(payload.get("brand_profile_id"))
        project = Project(
            name=payload.get("name") or payload.get("product_name") or "未命名作品",
            page_type=payload.get("page_type") or "main_image",
            platform=payload.get("platform") or "taobao",
            product_name=payload.get("product_name") or "",
            brand_profile_id=brand.id if brand else None,
            created_by=current_user.id,
        )
        self.db.add(project)
        self.db.commit()
        return self.get_project_detail(project.id, current_user)

    def delete_project(self, project_id: int, current_user: User) -> None:
        project = self._load_project(project_id, current_user)
        file_paths = self._collect_project_asset_paths(project)
        self.db.delete(project)
        self.db.commit()

        for file_path in file_paths:
            self._delete_storage_file(file_path)

    def get_project_detail(self, project_id: int, current_user: User) -> ProjectDetail:
        project = self._load_project(project_id, current_user)
        self._refresh_project_status(project)
        self.db.commit()
        self.db.refresh(project)
        project = self._load_project(project_id, current_user)
        return self._build_project_detail(project)

    def generate(
        self,
        *,
        project_id: int,
        payload: dict[str, Any],
        current_user: User,
        parent_version: Version | None = None,
        force_direct: bool = False,
    ) -> GenerationResult:
        project = self._load_project(project_id, current_user)
        brand = self._get_brand_profile(payload.get("brand_profile_id") or project.brand_profile_id)
        user_message = self._add_chat_message(project.id, "user", payload["message"], parent_version.id if parent_version else None)
        self.db.flush()

        guide_fields = payload.get("guide_fields") or {}
        previous_snapshot = parent_version.input_snapshot_json if parent_version else (project.versions[-1].input_snapshot_json if project.versions else {})
        user_turns = self._count_user_turns(project.id)
        plan = self.gateway.plan_generation(
            message=payload["message"],
            guide_fields=guide_fields,
            brand_context=self._build_brand_context(brand),
            previous_snapshot=previous_snapshot,
            project_defaults={
                "page_type": project.page_type,
                "platform": project.platform,
                "product_name": project.product_name,
            },
            user_turns=user_turns,
        )

        if plan["should_clarify"] and not force_direct:
            content = "为了更贴近你的创作目标，我还需要确认：\n" + "\n".join(
                f"{index + 1}. {question}" for index, question in enumerate(plan["questions"])
            )
            assistant_message = self._add_chat_message(project.id, "assistant", content, None)
            self.db.commit()
            project_detail = self.get_project_detail(project.id, current_user)
            return GenerationResult(
                mode="clarify",
                project=project_detail,
                assistant_message=assistant_message,
                version=None,
                questions=plan["questions"],
            )

        snapshot = dict(plan["snapshot"])
        project.brand_profile_id = brand.id
        if payload.get("source_image_path"):
            snapshot["source_image_path"] = payload["source_image_path"]
        elif previous_snapshot.get("source_image_path"):
            snapshot["source_image_path"] = previous_snapshot["source_image_path"]

        version = self._create_version(
            project=project,
            prompt_text=payload["message"],
            snapshot=snapshot,
            parent_version=parent_version,
        )
        assistant_text = f"已生成第 {version.version_no} 版主图，你可以继续告诉我想调整的主体、卖点、背景或版式。"
        assistant_message = self._add_chat_message(project.id, "assistant", assistant_text, version.id)
        user_message.version_id = version.id
        self._refresh_project_status(project)
        self.db.commit()

        project_detail = self.get_project_detail(project.id, current_user)
        version_detail = next(item for item in project_detail.versions if item.id == version.id)
        return GenerationResult(
            mode="generated",
            project=project_detail,
            assistant_message=assistant_message,
            version=version_detail,
            questions=[],
        )

    def regenerate(self, *, project_id: int, version_id: int, payload: dict[str, Any], current_user: User) -> GenerationResult:
        project = self._load_project(project_id, current_user)
        version = self._get_version(project, version_id)
        return self.generate(project_id=project.id, payload=payload, current_user=current_user, parent_version=version, force_direct=True)

    def review(self, *, project_id: int, version_id: int, action: str, comment: str, current_user: User) -> ProjectDetail:
        project = self._load_project(project_id, current_user)
        version = self._get_version(project, version_id)
        version.review_status = action
        version.review_comment = comment
        review_label = "已通过" if action == "approved" else "已驳回"
        review_comment = comment or "暂无补充意见。"
        self._add_chat_message(project.id, "assistant", f"审核结果：{review_label}。{review_comment}", version.id)
        self._refresh_project_status(project)
        self.db.commit()
        return self.get_project_detail(project.id, current_user)

    def finalize(self, *, project_id: int, version_id: int, current_user: User) -> ProjectDetail:
        project = self._load_project(project_id, current_user)
        version = self._get_version(project, version_id)
        if version.review_status != "approved":
            raise ValueError("只有通过审核的版本才能定稿。")
        for item in project.versions:
            item.is_final = item.id == version.id
        project.final_version_id = version.id
        self._add_chat_message(project.id, "assistant", f"第 {version.version_no} 版已定稿归档，可继续基于定稿版本派生新版本。", version.id)
        self._refresh_project_status(project)
        self.db.commit()
        return self.get_project_detail(project.id, current_user)

    def derive(self, *, project_id: int, version_id: int, payload: dict[str, Any], current_user: User) -> GenerationResult:
        project = self._load_project(project_id, current_user)
        version = self._get_version(project, version_id)
        if not version.is_final:
            raise ValueError("只有定稿版本才能继续派生。")
        return self.generate(project_id=project.id, payload=payload, current_user=current_user, parent_version=version, force_direct=True)

    def _create_version(
        self,
        *,
        project: Project,
        prompt_text: str,
        snapshot: dict[str, Any],
        parent_version: Version | None,
    ) -> Version:
        next_version_no = (project.versions[-1].version_no + 1) if project.versions else 1
        version = Version(
            project_id=project.id,
            version_no=next_version_no,
            prompt_text=prompt_text,
            title_text=snapshot.get("title_text", ""),
            review_status="unreviewed",
            parent_version_id=parent_version.id if parent_version else None,
            input_snapshot_json=snapshot,
        )
        self.db.add(version)
        self.db.flush()

        for asset_payload in self.image_pipeline.generate_assets(
            snapshot=snapshot,
            source_image_path=snapshot.get("source_image_path"),
        ):
            self.db.add(
                Asset(
                    version_id=version.id,
                    file_path=asset_payload["file_path"],
                    asset_type=asset_payload["asset_type"],
                    width=asset_payload.get("width"),
                    height=asset_payload.get("height"),
                )
            )

        project.name = snapshot.get("product_name") or project.name
        project.product_name = snapshot.get("product_name") or project.product_name
        project.page_type = snapshot.get("page_type") or project.page_type
        project.platform = snapshot.get("platform") or project.platform
        project.latest_version_id = version.id
        return version

    def _refresh_project_status(self, project: Project) -> None:
        latest_version = self._resolve_latest_version(project)
        if project.final_version_id or any(version.is_final for version in project.versions):
            project.status = "finalized"
            return
        if latest_version:
            mapping = {
                "unreviewed": "unreviewed",
                "approved": "approved",
                "rejected": "rejected",
            }
            project.status = mapping.get(latest_version.review_status, "unreviewed")
            return
        project.status = "unreviewed"

    def _load_project(self, project_id: int, current_user: User) -> Project:
        statement = (
            select(Project)
            .where(Project.id == project_id)
            .options(
                selectinload(Project.versions).selectinload(Version.assets),
                selectinload(Project.chat_messages),
            )
        )
        if current_user.role != "admin":
            statement = statement.where(Project.created_by == current_user.id)
        project = self.db.scalar(statement)
        if not project:
            raise ValueError("未找到对应作品。")
        return project

    def _get_version(self, project: Project, version_id: int) -> Version:
        version = next((item for item in project.versions if item.id == version_id), None)
        if not version:
            raise ValueError("未找到对应版本。")
        return version

    def _get_brand_profile(self, brand_profile_id: int | None) -> BrandProfile:
        if brand_profile_id:
            brand = self.db.scalar(select(BrandProfile).where(BrandProfile.id == brand_profile_id))
            if brand:
                return brand
        brand = self.db.scalar(select(BrandProfile).order_by(BrandProfile.id.asc()))
        if not brand:
            raise ValueError("未找到品牌资料。")
        return brand

    def _build_brand_context(self, brand: BrandProfile) -> DemoBrandContext:
        default_keywords = ["金属质感", "工业简洁", "耐腐蚀", "高强度", "支持定制"]
        return DemoBrandContext(
            name=self._safe_text(brand.name, settings.default_brand_name),
            description=self._safe_text(brand.description, settings.default_brand_description),
            style_summary=self._safe_text(brand.style_summary, "工业感、简洁排版、突出材质纹理和定制能力。"),
            recommended_keywords=self._safe_keywords(brand.recommended_keywords or [], default_keywords),
        )

    def _build_project_list_item(self, project: Project) -> ProjectListItem:
        latest_version = self._resolve_latest_version(project)
        cover_asset = self._select_cover_asset(latest_version)
        return ProjectListItem(
            id=project.id,
            name=project.name,
            page_type=project.page_type,
            platform=project.platform,
            product_name=project.product_name,
            status=project.status,
            latest_version_id=project.latest_version_id,
            final_version_id=project.final_version_id,
            created_at=project.created_at,
            cover_asset_path=cover_asset.file_path if cover_asset else None,
            cover_asset_type=cover_asset.asset_type if cover_asset else None,
            cover_width=cover_asset.width if cover_asset else None,
            cover_height=cover_asset.height if cover_asset else None,
            latest_version_no=latest_version.version_no if latest_version else None,
        )

    def _build_project_detail(self, project: Project) -> ProjectDetail:
        latest_version = self._resolve_latest_version(project)
        cover_asset = self._select_cover_asset(latest_version)
        detail = ProjectDetail.model_validate(project)
        return detail.model_copy(
            update={
                "cover_asset_path": cover_asset.file_path if cover_asset else None,
                "cover_asset_type": cover_asset.asset_type if cover_asset else None,
                "cover_width": cover_asset.width if cover_asset else None,
                "cover_height": cover_asset.height if cover_asset else None,
                "latest_version_no": latest_version.version_no if latest_version else None,
            }
        )

    def _resolve_latest_version(self, project: Project) -> Version | None:
        if project.latest_version_id:
            latest_version = next((item for item in project.versions if item.id == project.latest_version_id), None)
            if latest_version:
                return latest_version
        return project.versions[-1] if project.versions else None

    def _select_cover_asset(self, latest_version: Version | None) -> Asset | None:
        if not latest_version or not latest_version.assets:
            return None

        final_asset = next((asset for asset in latest_version.assets if asset.asset_type == "final_export"), None)
        if final_asset:
            return final_asset

        previewable_assets = [asset for asset in latest_version.assets if asset.asset_type in PREVIEWABLE_ASSET_TYPES]
        return previewable_assets[-1] if previewable_assets else None

    def _collect_project_asset_paths(self, project: Project) -> set[str]:
        paths: set[str] = set()
        for version in project.versions:
            for asset in version.assets:
                if asset.file_path:
                    paths.add(asset.file_path)

        for version in project.versions:
            source_path = version.input_snapshot_json.get("source_image_path")
            if isinstance(source_path, str) and source_path.strip():
                paths.add(source_path)
        return paths

    def _delete_storage_file(self, relative_path: str) -> None:
        if not relative_path:
            return
        absolute_path = Path(settings.storage_dir) / relative_path
        try:
            if absolute_path.exists() and absolute_path.is_file():
                absolute_path.unlink()
        except OSError:
            # Deletion failure should not block project removal.
            return

    def _add_chat_message(self, project_id: int, sender_type: str, content: str, version_id: int | None) -> ChatMessage:
        message = ChatMessage(project_id=project_id, sender_type=sender_type, content=content, version_id=version_id)
        self.db.add(message)
        self.db.flush()
        return message

    def _count_user_turns(self, project_id: int) -> int:
        messages = list(
            self.db.scalars(
                select(ChatMessage).where(ChatMessage.project_id == project_id, ChatMessage.sender_type == "user")
            )
        )
        return len(messages)

    def _safe_text(self, value: str | None, default: str) -> str:
        text = (value or "").strip()
        if not text or self._looks_broken_text(text):
            return default
        return text

    def _safe_keywords(self, values: list[str], default: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value and not self._looks_broken_text(value)]
        return cleaned or default

    def _looks_broken_text(self, value: str) -> bool:
        if value.count("?") >= 2:
            return True
        if "\ufffd" in value:
            return True
        suspicious_tokens = ("锛", "銆", "鈥", "锟", "鏄", "鐗", "鍝", "浣", "璇", "缁", "姝")
        return sum(token in value for token in suspicious_tokens) >= 2
