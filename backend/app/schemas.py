from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserSummary


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version_id: int
    file_path: str
    asset_type: str
    width: int | None
    height: int | None
    created_at: datetime


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    version_id: int | None
    sender_type: str
    content: str
    created_at: datetime


class VersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    version_no: int
    prompt_text: str
    title_text: str
    review_status: str
    review_comment: str
    is_final: bool
    parent_version_id: int | None
    input_snapshot_json: dict[str, Any]
    created_at: datetime
    assets: list[AssetRead] = Field(default_factory=list)


class ProjectListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    page_type: str
    platform: str
    product_name: str
    status: str
    latest_version_id: int | None
    final_version_id: int | None
    cover_asset_path: str | None = None
    cover_asset_type: str | None = None
    cover_width: int | None = None
    cover_height: int | None = None
    latest_version_no: int | None = None
    created_at: datetime


class ProjectDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    page_type: str
    platform: str
    product_name: str
    status: str
    latest_version_id: int | None
    final_version_id: int | None
    cover_asset_path: str | None = None
    cover_asset_type: str | None = None
    cover_width: int | None = None
    cover_height: int | None = None
    latest_version_no: int | None = None
    brand_profile_id: int | None
    created_at: datetime
    versions: list[VersionRead] = Field(default_factory=list)
    chat_messages: list[ChatMessageRead] = Field(default_factory=list)


class CreateProjectRequest(BaseModel):
    name: str | None = None
    page_type: Literal["main_image", "detail_module", "banner"] = "main_image"
    platform: Literal["taobao"] = "taobao"
    product_name: str | None = None
    brand_profile_id: int | None = None


class GenerateGuideFields(BaseModel):
    page_type: str | None = None
    platform: str | None = None
    product_name: str | None = None
    style_keywords: list[str] | None = None
    selling_points: list[str] | None = None


class GenerateProjectRequest(BaseModel):
    message: str
    guide_fields: GenerateGuideFields | None = None
    source_image_path: str | None = None
    brand_profile_id: int | None = None


class RegenerateVersionRequest(BaseModel):
    message: str
    guide_fields: GenerateGuideFields | None = None
    source_image_path: str | None = None
    brand_profile_id: int | None = None


class ReviewVersionRequest(BaseModel):
    action: Literal["approved", "rejected"]
    comment: str = ""


class ApiKeysRead(BaseModel):
    llm_api_key: str | None = None
    image_api_key: str | None = None
    cutout_api_key: str | None = None
    llm_api_key_source: Literal["env", "db", "unset"] = "unset"
    image_api_key_source: Literal["env", "db", "unset"] = "unset"
    cutout_api_key_source: Literal["env", "db", "unset"] = "unset"


class ApiKeysUpsertRequest(BaseModel):
    llm_api_key: str | None = None
    image_api_key: str | None = None
    cutout_api_key: str | None = None


class ProviderSettingsRead(BaseModel):
    llm_provider: str
    image_provider: str
    cutout_provider: str
    image_api_url: str | None = None
    image_model: str | None = None
    image_timeout_seconds: int = 60
    image_api_key_header: str = "Authorization"
    llm_provider_source: Literal["env", "db", "default", "unset"] = "default"
    image_provider_source: Literal["env", "db", "default", "unset"] = "default"
    cutout_provider_source: Literal["env", "db", "default", "unset"] = "default"
    image_api_url_source: Literal["env", "db", "default", "unset"] = "unset"
    image_model_source: Literal["env", "db", "default", "unset"] = "default"
    image_timeout_seconds_source: Literal["env", "db", "default", "unset"] = "default"
    image_api_key_header_source: Literal["env", "db", "default", "unset"] = "default"


class ProviderSettingsUpsertRequest(BaseModel):
    llm_provider: str
    image_provider: str
    cutout_provider: str
    image_api_url: str | None = None
    image_model: str | None = None
    image_timeout_seconds: int = 60
    image_api_key_header: str = "Authorization"


class ProviderTestResponse(BaseModel):
    ok: bool
    provider: str
    detail: str
    file_path: str | None = None


class BrandProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    style_summary: str
    recommended_keywords: list[str]


class BrandProfileUpsertRequest(BaseModel):
    name: str
    description: str
    style_summary: str | None = ""
    recommended_keywords: list[str] = Field(default_factory=list)


class BrandSummaryRequest(BaseModel):
    description: str


class BrandSummaryResponse(BaseModel):
    style_summary: str
    recommended_keywords: list[str]


class UploadImageResponse(BaseModel):
    file_path: str
    width: int | None
    height: int | None


class GenerationResult(BaseModel):
    mode: Literal["clarify", "generated"]
    project: ProjectDetail
    assistant_message: ChatMessageRead
    version: VersionRead | None = None
    questions: list[str] = Field(default_factory=list)
