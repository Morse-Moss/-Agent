from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.security import decrypt_secret, encrypt_secret, mask_secret
from ..models import SystemSetting

SourceType = Literal["env", "db", "default", "unset"]
PresetScope = Literal["llm", "image"]

SECRET_KEYS = {
    "llm_api_key": "LLM_API_KEY",
    "image_api_key": "IMAGE_API_KEY",
    "cutout_api_key": "CUTOUT_API_KEY",
}

PROVIDER_KEYS = {
    "llm_provider": ("LLM_PROVIDER", "local_demo"),
    "llm_api_url": ("LLM_API_URL", ""),
    "llm_model": ("LLM_MODEL", ""),
    "llm_timeout_seconds": ("LLM_TIMEOUT_SECONDS", "60"),
    "llm_api_key_header": ("LLM_API_KEY_HEADER", "Authorization"),
    "image_provider": ("IMAGE_PROVIDER", "local_demo"),
    "image_api_url": ("IMAGE_API_URL", ""),
    "image_model": ("IMAGE_MODEL", ""),
    "image_timeout_seconds": ("IMAGE_TIMEOUT_SECONDS", "60"),
    "image_api_key_header": ("IMAGE_API_KEY_HEADER", "Authorization"),
    "cutout_provider": ("CUTOUT_PROVIDER", "local_demo"),
}

PRESET_STORE_KEY = "PROVIDER_PRESETS_JSON"
PRESET_SCOPES: tuple[PresetScope, ...] = ("llm", "image")


@dataclass
class GatewayRuntimeConfig:
    llm_provider: str = "local_demo"
    llm_api_url: str | None = None
    llm_model: str | None = None
    llm_timeout_seconds: int = 60
    llm_api_key_header: str = "Authorization"
    image_provider: str = "local_demo"
    image_api_url: str | None = None
    image_model: str | None = None
    image_timeout_seconds: int = 60
    image_api_key_header: str = "Authorization"
    cutout_provider: str = "local_demo"
    llm_api_key: str | None = None
    image_api_key: str | None = None
    cutout_api_key: str | None = None


class SystemSettingsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def read_secret_masked(self, field_name: str) -> tuple[str | None, SourceType]:
        secret, source = self.read_secret_raw(field_name)
        if not secret:
            return None, source
        return mask_secret(secret), source

    def read_secret_raw(self, field_name: str) -> tuple[str | None, SourceType]:
        env_name = SECRET_KEYS[field_name]
        env_value = os.getenv(env_name)
        if env_value:
            return env_value, "env"
        setting = self._get_setting(env_name)
        if setting and setting.key_value:
            return decrypt_secret(setting.key_value), "db"
        return None, "unset"

    def write_secret(self, field_name: str, value: str) -> None:
        env_name = SECRET_KEYS[field_name]
        setting = self._get_or_create_setting(env_name)
        setting.key_value = encrypt_secret(value)

    def read_provider_value(self, field_name: str) -> tuple[str, SourceType]:
        env_name, default_value = PROVIDER_KEYS[field_name]
        env_value = os.getenv(env_name)
        if env_value is not None and env_value != "":
            return env_value, "env"
        setting = self._get_setting(env_name)
        if setting and setting.key_value:
            return setting.key_value, "db"
        if default_value != "":
            return default_value, "default"
        return "", "unset"

    def write_provider_value(self, field_name: str, value: str) -> None:
        env_name, _default_value = PROVIDER_KEYS[field_name]
        setting = self._get_or_create_setting(env_name)
        setting.key_value = value

    def build_gateway_runtime_config(self) -> GatewayRuntimeConfig:
        llm_provider, _ = self.read_provider_value("llm_provider")
        llm_api_url, _ = self.read_provider_value("llm_api_url")
        llm_model, _ = self.read_provider_value("llm_model")
        llm_timeout_seconds, _ = self.read_provider_value("llm_timeout_seconds")
        llm_api_key_header, _ = self.read_provider_value("llm_api_key_header")
        image_provider, _ = self.read_provider_value("image_provider")
        image_api_url, _ = self.read_provider_value("image_api_url")
        image_model, _ = self.read_provider_value("image_model")
        image_timeout_seconds, _ = self.read_provider_value("image_timeout_seconds")
        image_api_key_header, _ = self.read_provider_value("image_api_key_header")
        cutout_provider, _ = self.read_provider_value("cutout_provider")
        llm_api_key, _ = self.read_secret_raw("llm_api_key")
        image_api_key, _ = self.read_secret_raw("image_api_key")
        cutout_api_key, _ = self.read_secret_raw("cutout_api_key")

        return GatewayRuntimeConfig(
            llm_provider=llm_provider,
            llm_api_url=llm_api_url or None,
            llm_model=llm_model or None,
            llm_timeout_seconds=self._parse_timeout(llm_timeout_seconds),
            llm_api_key_header=llm_api_key_header or "Authorization",
            image_provider=image_provider,
            image_api_url=image_api_url or None,
            image_model=image_model or None,
            image_timeout_seconds=self._parse_timeout(image_timeout_seconds),
            image_api_key_header=image_api_key_header or "Authorization",
            cutout_provider=cutout_provider,
            llm_api_key=llm_api_key,
            image_api_key=image_api_key,
            cutout_api_key=cutout_api_key,
        )

    def list_provider_presets(self) -> dict[str, list[dict[str, Any]]]:
        store = self._load_preset_store()
        return {
            "llm_presets": [self._to_preset_read_model("llm", item) for item in store["llm"]],
            "image_presets": [self._to_preset_read_model("image", item) for item in store["image"]],
        }

    def save_provider_preset(
        self,
        *,
        scope: PresetScope,
        preset_name: str,
        provider: str,
        api_url: str | None,
        model: str | None,
        timeout_seconds: int,
        api_key_header: str,
        api_key: str | None = None,
        include_api_key: bool = True,
    ) -> dict[str, list[dict[str, Any]]]:
        normalized_name = preset_name.strip()
        if not normalized_name:
            raise ValueError("预设名称不能为空。")

        store = self._load_preset_store()
        presets = [item for item in store[scope] if item.get("preset_name") != normalized_name]

        encrypted_api_key = ""
        if include_api_key:
            effective_api_key = api_key
            if effective_api_key is None:
                secret_field = "llm_api_key" if scope == "llm" else "image_api_key"
                effective_api_key, _ = self.read_secret_raw(secret_field)
            if effective_api_key:
                encrypted_api_key = encrypt_secret(effective_api_key)

        presets.append(
            {
                "preset_name": normalized_name,
                "provider": provider.strip(),
                "api_url": (api_url or "").strip(),
                "model": (model or "").strip(),
                "timeout_seconds": self._parse_timeout(str(timeout_seconds)),
                "api_key_header": (api_key_header or "Authorization").strip() or "Authorization",
                "encrypted_api_key": encrypted_api_key,
            }
        )
        presets.sort(key=lambda item: item.get("preset_name", "").lower())
        store[scope] = presets
        self._write_preset_store(store)
        return self.list_provider_presets()

    def apply_provider_preset(self, *, scope: PresetScope, preset_name: str) -> None:
        preset = self._find_preset(scope, preset_name)
        if not preset:
            raise ValueError("未找到对应的模型预设。")

        if scope == "llm":
            self.write_provider_value("llm_provider", str(preset.get("provider", "")))
            self.write_provider_value("llm_api_url", str(preset.get("api_url", "")))
            self.write_provider_value("llm_model", str(preset.get("model", "")))
            self.write_provider_value("llm_timeout_seconds", str(preset.get("timeout_seconds", 60)))
            self.write_provider_value("llm_api_key_header", str(preset.get("api_key_header", "Authorization")))
            encrypted_api_key = str(preset.get("encrypted_api_key", ""))
            if encrypted_api_key:
                self.write_secret("llm_api_key", decrypt_secret(encrypted_api_key))
            return

        self.write_provider_value("image_provider", str(preset.get("provider", "")))
        self.write_provider_value("image_api_url", str(preset.get("api_url", "")))
        self.write_provider_value("image_model", str(preset.get("model", "")))
        self.write_provider_value("image_timeout_seconds", str(preset.get("timeout_seconds", 60)))
        self.write_provider_value("image_api_key_header", str(preset.get("api_key_header", "Authorization")))
        encrypted_api_key = str(preset.get("encrypted_api_key", ""))
        if encrypted_api_key:
            self.write_secret("image_api_key", decrypt_secret(encrypted_api_key))

    def delete_provider_preset(self, *, scope: PresetScope, preset_name: str) -> dict[str, list[dict[str, Any]]]:
        store = self._load_preset_store()
        before_count = len(store[scope])
        store[scope] = [item for item in store[scope] if item.get("preset_name") != preset_name]
        if len(store[scope]) == before_count:
            raise ValueError("未找到对应的模型预设。")
        self._write_preset_store(store)
        return self.list_provider_presets()

    def _find_preset(self, scope: PresetScope, preset_name: str) -> dict[str, Any] | None:
        store = self._load_preset_store()
        for item in store[scope]:
            if item.get("preset_name") == preset_name:
                return item
        return None

    def _load_preset_store(self) -> dict[str, list[dict[str, Any]]]:
        setting = self._get_setting(PRESET_STORE_KEY)
        default_store: dict[str, list[dict[str, Any]]] = {"llm": [], "image": []}
        if not setting or not setting.key_value:
            return default_store

        try:
            raw_data = json.loads(setting.key_value)
        except json.JSONDecodeError:
            return default_store

        normalized: dict[str, list[dict[str, Any]]] = {"llm": [], "image": []}
        for scope in PRESET_SCOPES:
            items = raw_data.get(scope, [])
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                preset_name = str(item.get("preset_name", "")).strip()
                provider = str(item.get("provider", "")).strip()
                if not preset_name or not provider:
                    continue
                normalized[scope].append(
                    {
                        "preset_name": preset_name,
                        "provider": provider,
                        "api_url": str(item.get("api_url", "") or "").strip(),
                        "model": str(item.get("model", "") or "").strip(),
                        "timeout_seconds": self._parse_timeout(str(item.get("timeout_seconds", 60))),
                        "api_key_header": str(item.get("api_key_header", "Authorization") or "Authorization").strip()
                        or "Authorization",
                        "encrypted_api_key": str(item.get("encrypted_api_key", "") or "").strip(),
                    }
                )
        return normalized

    def _write_preset_store(self, store: dict[str, list[dict[str, Any]]]) -> None:
        setting = self._get_or_create_setting(PRESET_STORE_KEY)
        setting.key_value = json.dumps(store, ensure_ascii=False, separators=(",", ":"))

    def _to_preset_read_model(self, scope: PresetScope, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "preset_name": str(item.get("preset_name", "")),
            "scope": scope,
            "provider": str(item.get("provider", "")),
            "api_url": str(item.get("api_url", "")) or None,
            "model": str(item.get("model", "")) or None,
            "timeout_seconds": self._parse_timeout(str(item.get("timeout_seconds", 60))),
            "api_key_header": str(item.get("api_key_header", "Authorization")) or "Authorization",
            "has_api_key": bool(item.get("encrypted_api_key")),
        }

    def _get_setting(self, key_name: str) -> SystemSetting | None:
        return self.db.scalar(select(SystemSetting).where(SystemSetting.key_name == key_name))

    def _get_or_create_setting(self, key_name: str) -> SystemSetting:
        setting = self._get_setting(key_name)
        if setting:
            return setting
        setting = SystemSetting(key_name=key_name, key_value="")
        self.db.add(setting)
        return setting

    def _parse_timeout(self, raw_value: str) -> int:
        try:
            return max(5, int(raw_value))
        except (TypeError, ValueError):
            return 60
