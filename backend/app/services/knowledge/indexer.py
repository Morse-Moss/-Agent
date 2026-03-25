"""Knowledge indexer — event-driven incremental indexing.

Indexes finalized versions and brand profile updates into Qdrant.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

from .embedder import Embedder
from .qdrant_client import QdrantManager

logger = logging.getLogger(__name__)


class KnowledgeIndexer:
    """Indexes content into Qdrant on business events."""

    def __init__(self, qdrant: QdrantManager, embedder: Embedder) -> None:
        self.qdrant = qdrant
        self.embedder = embedder

    @property
    def is_available(self) -> bool:
        return self.qdrant.is_available and self.embedder.is_available

    def index_finalized_version(
        self,
        *,
        version_id: int,
        project_id: int,
        brand_id: int | None,
        category_id: int | None,
        prompt_summary: str,
        title_text: str,
        product_name: str,
        style_keywords: list[str],
        output_type: str = "main_image",
    ) -> bool:
        """Index a finalized version's generation context."""
        if not self.is_available:
            return False

        text = f"{product_name} {title_text} {prompt_summary} {' '.join(style_keywords)}"
        vector = self.embedder.embed(text)
        if not vector:
            return False

        point_id = self._make_id("version", version_id)
        payload: dict[str, Any] = {
            "source_type": "version",
            "version_id": version_id,
            "project_id": project_id,
            "brand_id": brand_id,
            "category_id": category_id,
            "product_name": product_name,
            "prompt_summary": prompt_summary,
            "title_text": title_text,
            "style_keywords": style_keywords,
            "output_type": output_type,
        }

        success = self.qdrant.upsert(point_id, vector, payload)
        if success:
            logger.info("Indexed version %d into knowledge base", version_id)
        return success

    def index_brand_profile(
        self,
        *,
        brand_id: int,
        name: str,
        description: str,
        style_summary: str,
        keywords: list[str],
    ) -> bool:
        """Index or re-index a brand profile."""
        if not self.is_available:
            return False

        text = f"{name} {description} {style_summary} {' '.join(keywords)}"
        vector = self.embedder.embed(text)
        if not vector:
            return False

        point_id = self._make_id("brand", brand_id)
        payload: dict[str, Any] = {
            "source_type": "brand",
            "brand_id": brand_id,
            "name": name,
            "description": description,
            "style_summary": style_summary,
            "keywords": keywords,
        }

        success = self.qdrant.upsert(point_id, vector, payload)
        if success:
            logger.info("Indexed brand %d into knowledge base", brand_id)
        return success

    def _make_id(self, source_type: str, reference_id: int) -> str:
        """Generate a deterministic point ID."""
        raw = f"{source_type}:{reference_id}"
        return hashlib.md5(raw.encode()).hexdigest()
