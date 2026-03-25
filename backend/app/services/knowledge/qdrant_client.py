"""Qdrant client wrapper — connection and collection management."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

COLLECTION_NAME = "ecom_knowledge"
VECTOR_SIZE = 384  # sentence-transformers/all-MiniLM-L6-v2 default


class QdrantManager:
    """Manages Qdrant connection and collections."""

    def __init__(self, url: str | None = None) -> None:
        self.url = url
        self._client = None

    @property
    def is_available(self) -> bool:
        return self.url is not None and self._get_client() is not None

    def _get_client(self) -> Any | None:
        if self._client is not None:
            return self._client
        if not self.url:
            return None
        try:
            from qdrant_client import QdrantClient
            self._client = QdrantClient(url=self.url)
            return self._client
        except ImportError:
            logger.warning("qdrant-client not installed")
            return None
        except Exception:
            logger.exception("Failed to connect to Qdrant at %s", self.url)
            return None

    def ensure_collection(self) -> bool:
        """Create collection if it doesn't exist. Returns True on success."""
        client = self._get_client()
        if not client:
            return False
        try:
            from qdrant_client.models import Distance, VectorParams
            collections = [c.name for c in client.get_collections().collections]
            if COLLECTION_NAME not in collections:
                client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
                )
                logger.info("Created Qdrant collection: %s", COLLECTION_NAME)
            return True
        except Exception:
            logger.exception("Failed to ensure Qdrant collection")
            return False

    def upsert(self, point_id: str, vector: list[float], payload: dict[str, Any]) -> bool:
        """Insert or update a point."""
        client = self._get_client()
        if not client:
            return False
        try:
            from qdrant_client.models import PointStruct
            client.upsert(
                collection_name=COLLECTION_NAME,
                points=[PointStruct(id=point_id, vector=vector, payload=payload)],
            )
            return True
        except Exception:
            logger.exception("Failed to upsert point %s", point_id)
            return False

    def search(
        self,
        vector: list[float],
        limit: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar vectors with optional payload filters."""
        client = self._get_client()
        if not client:
            return []
        try:
            query_filter = None
            if filters:
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                conditions = [
                    FieldCondition(key=k, match=MatchValue(value=v))
                    for k, v in filters.items()
                ]
                query_filter = Filter(must=conditions)

            results = client.search(
                collection_name=COLLECTION_NAME,
                query_vector=vector,
                limit=limit,
                query_filter=query_filter,
            )
            return [
                {"id": str(r.id), "score": r.score, "payload": r.payload}
                for r in results
            ]
        except Exception:
            logger.exception("Qdrant search failed")
            return []
