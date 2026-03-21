from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.security import mask_secret, xor_cipher, xor_decipher
from ..models import SystemSetting

SourceType = Literal["env", "db", "default", "unset"]

SECRET_KEYS = {
    "llm_api_key": "LLM_API_KEY",
    "image_api_key": "IMAGE_API_KEY",
    "cutout_api_key": "CUTOUT_API_KEY",
}

PROVIDER_KEYS = {
    "llm_provider": ("LLM_PROVIDER", "local_demo"),
    "image_provider": ("IMAGE_PROVIDER", "local_demo"),
    "cutout_provider": ("CUTOUT_PROVIDER", "local_demo"),
    "image_api_url": ("IMAGE_API_URL", ""),
    "image_model": ("IMAGE_MODEL", "demo-main-image"),
    "image_timeout_seconds": ("IMAGE_TIMEOUT_SECONDS", "60"),
    "image_api_key_header": ("IMAGE_API_KEY_HEADER", "Authorization"),
}


@dataclass
class GatewayRuntimeConfig:
    llm_provider: str = "local_demo"
    image_provider: str = "local_demo"
    cutout_provider: str = "local_demo"
    image_api_url: str | None = None
    image_model: str | None = None
    image_timeout_seconds: int = 60
    image_api_key_header: str = "Authorization"
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
        setting = self.db.scalar(select(SystemSetting).where(SystemSetting.key_name == env_name))
        if setting:
            return xor_decipher(setting.key_value), "db"
        return None, "unset"

    def write_secret(self, field_name: str, value: str) -> None:
        env_name = SECRET_KEYS[field_name]
        setting = self.db.scalar(select(SystemSetting).where(SystemSetting.key_name == env_name))
        if not setting:
            setting = SystemSetting(key_name=env_name, key_value="")
            self.db.add(setting)
        setting.key_value = xor_cipher(value)

    def read_provider_value(self, field_name: str) -> tuple[str, SourceType]:
        env_name, default_value = PROVIDER_KEYS[field_name]
        env_value = os.getenv(env_name)
        if env_value is not None and env_value != "":
            return env_value, "env"
        setting = self.db.scalar(select(SystemSetting).where(SystemSetting.key_name == env_name))
        if setting and setting.key_value:
            return setting.key_value, "db"
        if default_value != "":
            return default_value, "default"
        return "", "unset"

    def write_provider_value(self, field_name: str, value: str) -> None:
        env_name, _default_value = PROVIDER_KEYS[field_name]
        setting = self.db.scalar(select(SystemSetting).where(SystemSetting.key_name == env_name))
        if not setting:
            setting = SystemSetting(key_name=env_name, key_value="")
            self.db.add(setting)
        setting.key_value = value

    def build_gateway_runtime_config(self) -> GatewayRuntimeConfig:
        llm_provider, _ = self.read_provider_value("llm_provider")
        image_provider, _ = self.read_provider_value("image_provider")
        cutout_provider, _ = self.read_provider_value("cutout_provider")
        image_api_url, _ = self.read_provider_value("image_api_url")
        image_model, _ = self.read_provider_value("image_model")
        image_timeout_seconds, _ = self.read_provider_value("image_timeout_seconds")
        image_api_key_header, _ = self.read_provider_value("image_api_key_header")
        llm_api_key, _ = self.read_secret_raw("llm_api_key")
        image_api_key, _ = self.read_secret_raw("image_api_key")
        cutout_api_key, _ = self.read_secret_raw("cutout_api_key")
        timeout_seconds = 60
        try:
            timeout_seconds = max(5, int(image_timeout_seconds))
        except ValueError:
            timeout_seconds = 60

        return GatewayRuntimeConfig(
            llm_provider=llm_provider,
            image_provider=image_provider,
            cutout_provider=cutout_provider,
            image_api_url=image_api_url or None,
            image_model=image_model or None,
            image_timeout_seconds=timeout_seconds,
            image_api_key_header=image_api_key_header or "Authorization",
            llm_api_key=llm_api_key,
            image_api_key=image_api_key,
            cutout_api_key=cutout_api_key,
        )
