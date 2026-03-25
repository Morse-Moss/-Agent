"""Knowledge base API routes — search and stats."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...api.dependencies import get_current_user
from ...core.config import settings as app_settings
from ...db import get_db
from ...models import User
from ...services.knowledge.embedder import Embedder
from ...services.knowledge.qdrant_client import QdrantManager
from ...services.knowledge.rag_pipeline import RAGPipeline

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _get_rag() -> RAGPipeline:
    qdrant = QdrantManager(url=app_settings.qdrant_url)
    embedder = Embedder()
    return RAGPipeline(qdrant, embedder)


@router.get("/search")
def search_knowledge(
    q: str,
    brand_id: int | None = None,
    category_id: int | None = None,
    output_type: str | None = None,
    limit: int = 5,
    user: User = Depends(get_current_user),
) -> dict:
    rag = _get_rag()
    if not rag.is_available:
        return {"results": [], "message": "Knowledge base not available (Qdrant not configured)"}

    results = rag.retrieve(
        q,
        brand_id=brand_id,
        category_id=category_id,
        output_type=output_type,
        limit=limit,
    )
    return {"results": results}


@router.get("/status")
def knowledge_status(
    user: User = Depends(get_current_user),
) -> dict:
    qdrant = QdrantManager(url=app_settings.qdrant_url)
    return {
        "qdrant_configured": app_settings.qdrant_url is not None,
        "qdrant_available": qdrant.is_available,
    }
