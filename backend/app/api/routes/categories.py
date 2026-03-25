"""Product category API routes — CRUD for configurable category tree.

P0/P1 fixes: cycle detection on parent_id, soft delete strategy.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...api.dependencies import get_current_user
from ...db import get_db
from ...models import ProductCategory, User
from ...schemas import ProductCategoryCreate, ProductCategoryRead, ProductCategoryUpdate

router = APIRouter(prefix="/categories", tags=["categories"])


def _would_create_cycle(db: Session, category_id: int, new_parent_id: int | None) -> bool:
    """Check if setting parent_id would create a cycle in the category tree."""
    if new_parent_id is None:
        return False
    if new_parent_id == category_id:
        return True  # Self-reference

    # Walk up the tree from new_parent_id; if we reach category_id, it's a cycle
    visited: set[int] = set()
    current_id: int | None = new_parent_id
    while current_id is not None:
        if current_id in visited:
            return True  # Already a cycle in the tree
        if current_id == category_id:
            return True
        visited.add(current_id)
        parent = db.get(ProductCategory, current_id)
        current_id = parent.parent_id if parent else None
    return False


@router.get("", response_model=list[ProductCategoryRead])
def list_categories(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ProductCategoryRead]:
    """Return flat list of all active categories (frontend builds tree)."""
    cats = db.scalars(
        select(ProductCategory)
        .where(ProductCategory.is_active.is_(True))
        .order_by(ProductCategory.sort_order, ProductCategory.id)
    ).all()
    return [ProductCategoryRead.model_validate(c) for c in cats]


@router.post("", response_model=ProductCategoryRead)
def create_category(
    body: ProductCategoryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProductCategoryRead:
    # Validate parent exists if specified
    if body.parent_id is not None:
        parent = db.get(ProductCategory, body.parent_id)
        if not parent:
            raise HTTPException(status_code=404, detail="Parent category not found")

    cat = ProductCategory(**body.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return ProductCategoryRead.model_validate(cat)


@router.put("/{category_id}", response_model=ProductCategoryRead)
def update_category(
    category_id: int,
    body: ProductCategoryUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProductCategoryRead:
    cat = db.get(ProductCategory, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    # Cycle detection if parent_id is being changed
    if body.parent_id is not None and body.parent_id != cat.parent_id:
        if _would_create_cycle(db, category_id, body.parent_id):
            raise HTTPException(
                status_code=422,
                detail="Cannot set parent: would create a cycle in the category tree"
            )

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(cat, field, value)
    db.commit()
    db.refresh(cat)
    return ProductCategoryRead.model_validate(cat)


@router.delete("/{category_id}")
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Soft-delete a category (set is_active=False). Children are reparented to parent."""
    cat = db.get(ProductCategory, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    # Reparent children to this category's parent
    children = db.scalars(
        select(ProductCategory).where(ProductCategory.parent_id == category_id)
    ).all()
    for child in children:
        child.parent_id = cat.parent_id

    cat.is_active = False
    db.commit()
    return {"ok": True, "detail": f"Category {category_id} deactivated, {len(children)} children reparented"}
