"""Abstract base adapter for product data crawling.

Supports dual-track: official API first, Playwright fallback.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CrawlResult:
    """Standardized result from any crawl adapter."""
    product_name: str = ""
    image_urls: list[str] = field(default_factory=list)
    price: str = ""
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    success: bool = False
    error: str = ""


class BaseCrawlAdapter(ABC):
    """Base class for platform-specific crawl adapters."""

    platform: str = "unknown"

    @abstractmethod
    async def crawl(self, url: str) -> CrawlResult:
        """Crawl a product page and return structured data."""
        ...

    @classmethod
    def can_handle(cls, url: str) -> bool:
        """Check if this adapter can handle the given URL."""
        return False
