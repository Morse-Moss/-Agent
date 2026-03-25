from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...db import get_db
from ...schemas import (
    ApiKeysRead,
    ApiKeysUpsertRequest,
    ProviderPresetApplyRequest,
    ProviderPresetSaveRequest,
    ProviderPresetsRead,
    ProviderSettingsRead,
    ProviderSettingsUpsertRequest,
    ProviderTestResponse,
)
from ...services.model_gateway import ModelGateway
from ...services.storage import StorageService
from ...services.system_settings import PROVIDER_KEYS, SECRET_KEYS, SystemSettingsService
from ..dependencies import get_current_user

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/api-keys", response_model=ApiKeysRead)
def get_api_keys(
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
) -> ApiKeysRead:
    service = SystemSettingsService(db)
    response: dict[str, str | None] = {}
    for field_name in SECRET_KEYS:
        masked, source = service.read_secret_masked(field_name)
        response[field_name] = masked
        response[f"{field_name}_source"] = source
    return ApiKeysRead(**response)


@router.post("/api-keys", response_model=ApiKeysRead)
def upsert_api_keys(
    payload: ApiKeysUpsertRequest,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
) -> ApiKeysRead:
    service = SystemSettingsService(db)
    for field_name in SECRET_KEYS:
        value = getattr(payload, field_name)
        if value is None:
            continue
        service.write_secret(field_name, value)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return get_api_keys(db)


@router.get("/providers", response_model=ProviderSettingsRead)
def get_provider_settings(
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
) -> ProviderSettingsRead:
    service = SystemSettingsService(db)
    response: dict[str, str | int | None] = {}
    for field_name in PROVIDER_KEYS:
        value, source = service.read_provider_value(field_name)
        if field_name.endswith("_timeout_seconds"):
            try:
                response[field_name] = int(value)
            except ValueError:
                response[field_name] = 60
        elif field_name.endswith("_api_url"):
            response[field_name] = value or None
        else:
            response[field_name] = value
        response[f"{field_name}_source"] = source
    return ProviderSettingsRead(**response)


@router.post("/providers", response_model=ProviderSettingsRead)
def upsert_provider_settings(
    payload: ProviderSettingsUpsertRequest,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
) -> ProviderSettingsRead:
    service = SystemSettingsService(db)
    values = payload.model_dump()
    for field_name in PROVIDER_KEYS:
        value = values[field_name]
        service.write_provider_value(field_name, "" if value is None else str(value))
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return get_provider_settings(db)


@router.get("/provider-presets", response_model=ProviderPresetsRead)
def get_provider_presets(
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
) -> ProviderPresetsRead:
    service = SystemSettingsService(db)
    return ProviderPresetsRead(**service.list_provider_presets())


@router.post("/provider-presets", response_model=ProviderPresetsRead)
def save_provider_preset(
    payload: ProviderPresetSaveRequest,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
) -> ProviderPresetsRead:
    service = SystemSettingsService(db)
    presets = service.save_provider_preset(
        scope=payload.scope,
        preset_name=payload.preset_name,
        provider=payload.provider,
        api_url=payload.api_url,
        model=payload.model,
        timeout_seconds=payload.timeout_seconds,
        api_key_header=payload.api_key_header,
        api_key=payload.api_key,
        include_api_key=payload.include_api_key,
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return ProviderPresetsRead(**presets)


@router.post("/provider-presets/apply", response_model=ProviderSettingsRead)
def apply_provider_preset(
    payload: ProviderPresetApplyRequest,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
) -> ProviderSettingsRead:
    service = SystemSettingsService(db)
    service.apply_provider_preset(scope=payload.scope, preset_name=payload.preset_name)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return get_provider_settings(db)


@router.post("/provider-presets/delete", response_model=ProviderPresetsRead)
def delete_provider_preset(
    payload: ProviderPresetApplyRequest,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
) -> ProviderPresetsRead:
    service = SystemSettingsService(db)
    presets = service.delete_provider_preset(scope=payload.scope, preset_name=payload.preset_name)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return ProviderPresetsRead(**presets)


@router.post("/providers/test-llm", response_model=ProviderTestResponse)
def test_llm_provider(
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
) -> ProviderTestResponse:
    service = SystemSettingsService(db)
    runtime_config = service.build_gateway_runtime_config()
    gateway = ModelGateway(runtime_config=runtime_config)
    try:
        result = gateway.test_llm_provider()
        return ProviderTestResponse(ok=True, provider=runtime_config.llm_provider, detail=result)
    except Exception as exc:
        return ProviderTestResponse(ok=False, provider=runtime_config.llm_provider, detail=str(exc))


@router.post("/providers/test-image", response_model=ProviderTestResponse)
def test_image_provider(
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
) -> ProviderTestResponse:
    service = SystemSettingsService(db)
    runtime_config = service.build_gateway_runtime_config()
    gateway = ModelGateway(runtime_config=runtime_config)

    snapshot = {
        "product_name": "广告材料铝材",
        "brand_name": "铝域精选",
        "style_keywords": ["工业简洁", "高级质感"],
        "selling_points": ["耐腐蚀", "支持定制"],
        "page_type": "main_image",
        "latest_user_message": "请生成一版淘宝商品主图，整体偏工业高级感和金属质感。",
    }

    provider_name = runtime_config.image_provider
    if provider_name == "local_demo":
        return ProviderTestResponse(
            ok=True,
            provider=provider_name,
            detail="当前使用的是本地演示生图模式，系统会返回本地渲染的占位图。",
        )

    try:
        image = gateway.call_image_provider(snapshot, (1200, 1200))
        if image is None:
            return ProviderTestResponse(
                ok=False,
                provider=provider_name,
                detail="图片 Provider 没有返回可用图片。",
            )

        if image.size != (1200, 1200):
            resized = image.resize((1200, 1200))
            image.close()
            image = resized

        storage = StorageService()
        saved = storage.save_image(image, bucket="processed")
        image.close()
        return ProviderTestResponse(
            ok=True,
            provider=provider_name,
            detail="图片 Provider 测试成功。",
            file_path=saved["file_path"],
        )
    except Exception as exc:
        return ProviderTestResponse(ok=False, provider=provider_name, detail=str(exc))
