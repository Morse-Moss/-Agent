"""ARQ worker — async task processing for crawling and video generation.

Start with: arq app.services.crawler.worker.WorkerSettings
Requires Redis.
"""
from __future__ import annotations

import logging
from typing import Any

from ..crawler.adapters.alibaba_1688 import Alibaba1688Adapter
from ..crawler.adapters.taobao import TaobaoAdapter
from ..crawler.adapters.base import BaseCrawlAdapter, CrawlResult

logger = logging.getLogger(__name__)

# Adapter registry
ADAPTERS: list[type[BaseCrawlAdapter]] = [Alibaba1688Adapter, TaobaoAdapter]


def _get_adapter(url: str) -> BaseCrawlAdapter | None:
    for adapter_cls in ADAPTERS:
        if adapter_cls.can_handle(url):
            return adapter_cls()
    return None


async def crawl_competitor_page(ctx: dict[str, Any], crawl_run_id: int) -> dict[str, Any]:
    """ARQ task: crawl a competitor product page and create candidates."""
    from ...db import SessionLocal
    from ...models import Candidate, CrawlRun
    from ...services.storage import StorageService
    from ...core.config import settings

    logger.info("Starting crawl for crawl_run_id=%d", crawl_run_id)

    with SessionLocal() as db:
        crawl_run = db.get(CrawlRun, crawl_run_id)
        if not crawl_run:
            logger.error("CrawlRun %d not found", crawl_run_id)
            return {"error": "CrawlRun not found"}

        crawl_run.status = "running"
        db.commit()

        adapter = _get_adapter(crawl_run.source_url)
        if not adapter:
            crawl_run.status = "failed"
            crawl_run.error_message = "No adapter found for URL"
            db.commit()
            return {"error": "No adapter for URL"}

        try:
            result: CrawlResult = await adapter.crawl(crawl_run.source_url)
        except Exception as exc:
            logger.exception("Crawl failed for %s", crawl_run.source_url)
            crawl_run.status = "failed"
            crawl_run.error_message = str(exc)
            db.commit()
            return {"error": str(exc)}

        if not result.success:
            crawl_run.status = "failed"
            crawl_run.error_message = result.error
            db.commit()
            return {"error": result.error}

        # Download images and create candidates
        storage = StorageService(settings.storage_dir)
        candidates_created = 0

        for idx, image_url in enumerate(result.image_urls[:9]):  # max 9
            try:
                file_path = await _download_and_save(image_url, storage)
                if file_path:
                    candidate = Candidate(
                        task_id=crawl_run.task_id,
                        source_type="crawled",
                        file_path=file_path,
                        metadata_json={
                            "source_url": image_url,
                            "product_name": result.product_name,
                            "index": idx,
                        },
                    )
                    db.add(candidate)
                    candidates_created += 1
            except Exception:
                logger.exception("Failed to download image %s", image_url)

        crawl_run.status = "completed"
        crawl_run.result_json = {
            "product_name": result.product_name,
            "price": result.price,
            "image_count": len(result.image_urls),
            "candidates_created": candidates_created,
        }
        db.commit()

        logger.info("Crawl completed: %d candidates created", candidates_created)
        return crawl_run.result_json


async def _download_and_save(url: str, storage: StorageService) -> str | None:
    """Download an image URL and save to storage."""
    import httpx
    from PIL import Image
    from io import BytesIO

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    img = Image.open(BytesIO(resp.content))
    result = storage.save_image(img, bucket="uploads")
    img.close()
    return result.get("file_path")


class WorkerSettings:
    """ARQ worker settings."""
    functions = [crawl_competitor_page]
    redis_settings = None  # Set at runtime from config

    @staticmethod
    def on_startup(ctx: dict[str, Any]) -> None:
        logger.info("ARQ worker started")

    @staticmethod
    def on_shutdown(ctx: dict[str, Any]) -> None:
        logger.info("ARQ worker stopped")
