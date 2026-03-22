from __future__ import annotations

from sqlalchemy import select

from backend.app.db import SessionLocal
from backend.app.models import BrandProfile


def main() -> int:
    with SessionLocal() as session:
        brand = session.scalar(select(BrandProfile).order_by(BrandProfile.id.asc()))
        if not brand:
            brand = BrandProfile()
            session.add(brand)

        brand.name = "铝域精选"
        brand.description = "专注广告材料铝材，强调工业品质、稳定供货和支持定制。"
        brand.style_summary = "工业高级感、排版克制、强调材质纹理和定制能力。"
        brand.recommended_keywords = ["金属质感", "工业简洁", "耐腐蚀", "高强度", "支持定制"]
        session.commit()
    print("brand profile repaired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
