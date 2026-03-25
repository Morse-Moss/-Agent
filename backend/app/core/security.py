from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from .config import settings

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 600_000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt, stored = password_hash.split("$", 1)
    except ValueError:
        return False
    for iterations in (600_000, 120_000):
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
        if hmac.compare_digest(digest.hex(), stored):
            return True
    return False


def create_access_token(subject: dict[str, Any], ttl_hours: int | None = None) -> str:
    expires_in = ttl_hours or settings.token_ttl_hours
    payload = {
        "sub": subject,
        "exp": int((_utc_now() + timedelta(hours=expires_in)).timestamp()),
    }
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    body = base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")
    signature = hmac.new(settings.secret_key.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
    token_sig = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")
    return f"{body}.{token_sig}"


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        body, token_sig = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("Invalid token format") from exc

    expected_sig = hmac.new(settings.secret_key.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
    expected_sig_encoded = base64.urlsafe_b64encode(expected_sig).decode("utf-8").rstrip("=")
    if not hmac.compare_digest(expected_sig_encoded, token_sig):
        raise ValueError("Invalid token signature")

    padding = "=" * (-len(body) % 4)
    payload = json.loads(base64.urlsafe_b64decode((body + padding).encode("utf-8")).decode("utf-8"))
    if int(payload.get("exp", 0)) < int(_utc_now().timestamp()):
        raise ValueError("Token has expired")
    return payload["sub"]


def _derive_fernet_key() -> bytes:
    """Derive a Fernet-compatible key from the app secret key via PBKDF2."""
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        settings.secret_key.encode("utf-8"),
        b"ecom-art-agent-fernet-salt",
        100_000,
    )
    return base64.urlsafe_b64encode(dk)


def encrypt_secret(secret_value: str) -> str:
    """Encrypt a secret value using Fernet (AES-128-CBC + HMAC)."""
    fernet = Fernet(_derive_fernet_key())
    return fernet.encrypt(secret_value.encode("utf-8")).decode("utf-8")


def decrypt_secret(encrypted_value: str) -> str:
    """Decrypt a Fernet-encrypted value. Falls back to legacy XOR for migration."""
    fernet = Fernet(_derive_fernet_key())
    try:
        return fernet.decrypt(encrypted_value.encode("utf-8")).decode("utf-8")
    except (InvalidToken, Exception):
        pass
    # Legacy XOR fallback for values encrypted before migration
    try:
        return _xor_decipher_legacy(encrypted_value)
    except Exception:
        logger.warning("Failed to decrypt secret with both Fernet and legacy XOR")
        return ""


def _xor_decipher_legacy(secret_value: str) -> str:
    key = settings.secret_key.encode("utf-8")
    raw = base64.urlsafe_b64decode(secret_value.encode("utf-8"))
    decrypted = bytes(raw[index] ^ key[index % len(key)] for index in range(len(raw)))
    return decrypted.decode("utf-8")


def mask_secret(secret_value: str) -> str:
    if len(secret_value) <= 8:
        return "*" * len(secret_value)
    return f"{secret_value[:4]}{'*' * (len(secret_value) - 8)}{secret_value[-4:]}"
