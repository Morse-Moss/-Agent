"""Shared text utilities used across services and database initialization."""

from __future__ import annotations

BROKEN_TEXT_TOKENS = ("锟", "\ufffd", "鏈", "宸", "褰撳", "娣", "闂")


def looks_broken_text(value: str | None) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    if not text:
        return True
    if text.count("?") >= 2:
        return True
    if "\ufffd" in text:
        return True
    return sum(token in text for token in BROKEN_TEXT_TOKENS) >= 2
