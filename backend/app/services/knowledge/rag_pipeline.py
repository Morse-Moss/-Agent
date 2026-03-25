"""RAG pipeline — Hybrid retrieval with strong filtering."""
from __future__ import annotations

import logging
from typing import Any

from .embedder import Embedder
from .qdrant_client import QdrantManager

logger = logging.getLogger(__name__)


class RAGPipeline:
    """Hybrid RAG: vector similarity + payload filtering (brand, category, output_type)."""

    def __init__(self, qdrant: QdrantManager, embedder: Embedder) -> None:
        self.qdrant = qdrant
        self.embedder = embedder

    @property
    def is_available(self) -> bool:
        return self.qdrant.is_available and self.embedder.is_available

    def retrieve(
        self,
        query: str,
        *,
        brand_id: int | None = None,
        category_id: int | None = None,
        output_type: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Retrieve relevant knowledge entries for a generation context.

        Applies strong filtering on brand/category/output_type before
        vector similarity ranking.
        """
        if not self.is_available:
            logger.debug("RAG pipeline not available, returning empty results")
            return []

        vector = self.embedder.embed(query)
        if not vector:
            return []

        # Build payload filters
        filters: dict[str, Any] = {}
        if brand_id is not None:
            filters["brand_id"] = brand_id
        if category_id is not None:
            filters["category_id"] = category_id
        if output_type:
            filters["output_type"] = output_type

        results = self.qdrant.search(vector=vector, limit=limit, filters=filters or None)
        logger.info("RAG retrieved %d results for query: %s...", len(results), query[:50])
        return results

    def build_context(self, results: list[dict[str, Any]]) -> str:
        """Format RAG results into a context string for LLM injection."""
        if not results:
            return ""

        lines = ["以下是相关的历史生成参考："]
        for i, r in enumerate(results, 1):
            payload = r.get("payload", {})
            score = r.get("score", 0)
            prompt = payload.get("prompt_summary", "")
            category = payload.get("category_name", "")
            lines.append(f"{i}. [{category}] {prompt} (相关度: {score:.2f})")

        return "\n".join(lines)
