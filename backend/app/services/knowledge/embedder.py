"""Text embedder — vectorize text for Qdrant storage and search."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class Embedder:
    """Generates text embeddings using sentence-transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self.model_name = model_name
        self._model = None

    def _get_model(self) -> Any | None:
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            logger.info("Loaded embedding model: %s", self.model_name)
            return self._model
        except ImportError:
            logger.warning("sentence-transformers not installed")
            return None
        except Exception:
            logger.exception("Failed to load embedding model")
            return None

    @property
    def is_available(self) -> bool:
        return self._get_model() is not None

    def embed(self, text: str) -> list[float] | None:
        """Embed a single text string. Returns vector or None."""
        model = self._get_model()
        if not model:
            return None
        try:
            vector = model.encode(text, normalize_embeddings=True)
            return vector.tolist()
        except Exception:
            logger.exception("Embedding failed for text: %s...", text[:50])
            return None

    def embed_batch(self, texts: list[str]) -> list[list[float]] | None:
        """Embed multiple texts. Returns list of vectors or None."""
        model = self._get_model()
        if not model:
            return None
        try:
            vectors = model.encode(texts, normalize_embeddings=True)
            return [v.tolist() for v in vectors]
        except Exception:
            logger.exception("Batch embedding failed")
            return None
