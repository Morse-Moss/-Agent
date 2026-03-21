from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db import get_db
from ...models import BrandProfile
from ...schemas import (
    BrandProfileRead,
    BrandProfileUpsertRequest,
    BrandSummaryRequest,
    BrandSummaryResponse,
)
from ...services.model_gateway import ModelGateway
from ..dependencies import get_current_user

router = APIRouter(prefix="/brand", tags=["brand"])


@router.get("/profile", response_model=BrandProfileRead)
def get_brand_profile(
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
) -> BrandProfileRead:
    brand = db.scalar(select(BrandProfile).order_by(BrandProfile.id.asc()))
    return BrandProfileRead.model_validate(brand)


@router.post("/profile", response_model=BrandProfileRead)
def upsert_brand_profile(
    payload: BrandProfileUpsertRequest,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
) -> BrandProfileRead:
    brand = db.scalar(select(BrandProfile).order_by(BrandProfile.id.asc()))
    if not brand:
        brand = BrandProfile()
        db.add(brand)
    brand.name = payload.name
    brand.description = payload.description
    brand.style_summary = payload.style_summary or ""
    brand.recommended_keywords = payload.recommended_keywords
    db.commit()
    db.refresh(brand)
    return BrandProfileRead.model_validate(brand)


@router.post("/profile/summarize", response_model=BrandSummaryResponse)
def summarize_brand_profile(
    payload: BrandSummaryRequest,
    _current_user=Depends(get_current_user),
) -> BrandSummaryResponse:
    gateway = ModelGateway()
    result = gateway.summarize_brand(payload.description)
    return BrandSummaryResponse(**result)
