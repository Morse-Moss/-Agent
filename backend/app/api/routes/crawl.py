"""Crawl API routes — enqueue crawl tasks and check status.

P0 fix: SSRF protection on source_url (block private/loopback/link-local).
"""
from __future__ import annotations

import ipaddress
import logging
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...api.dependencies import get_current_user
from ...core.config import settings as app_settings
from ...db import get_db
from ...models import CrawlRun, Task, User
from ...schemas import CrawlRunRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["crawl"])

# Allowed URL schemes and domain suffixes for crawling
_ALLOWED_SCHEMES = {"http", "https"}
_ALLOWED_DOMAINS = {
    "1688.com", "taobao.com", "tmall.com",
    "detail.1688.com", "item.taobao.com",
}


def _validate_crawl_url(url: str) -> tuple[bool, str]:
    """Validate URL is safe to crawl (SSRF protection).

    Blocks: private IPs, loopback, link-local, non-HTTP schemes,
    non-whitelisted domains.
    """
    if not url or not url.strip():
        return False, "URL is empty"

    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False, "Invalid URL format"

    # Scheme check
    if parsed.scheme not in _ALLOWED_SCHEMES:
        return False, f"Scheme '{parsed.scheme}' not allowed. Use http or https."

    hostname = parsed.hostname
    if not hostname:
        return False, "No hostname in URL"

    # Block IP addresses directly (prevent SSRF via IP)
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False, "Private/loopback/link-local IP addresses are not allowed"
        # Even public IPs are suspicious for e-commerce crawling
        return False, "Direct IP addresses are not allowed. Use domain names."
    except ValueError:
        pass  # Not an IP, it's a hostname — continue

    # Domain whitelist check
    hostname_lower = hostname.lower()
    domain_ok = any(
        hostname_lower == d or hostname_lower.endswith("." + d)
        for d in _ALLOWED_DOMAINS
    )
    if not domain_ok:
        return False, f"Domain '{hostname}' is not in the allowed list: {_ALLOWED_DOMAINS}"

    # Block localhost aliases
    if hostname_lower in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        return False, "Localhost is not allowed"

    return True, "ok"


@router.post("/{task_id}/crawl", response_model=CrawlRunRead)
async def start_crawl(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CrawlRunRead:
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.entry_type != "competitor_link":
        raise HTTPException(status_code=400, detail="Task is not a competitor_link type")

    source_url = task.task_config_json.get("source_url", "")

    # SSRF protection: validate URL before crawling
    url_ok, url_reason = _validate_crawl_url(source_url)
    if not url_ok:
        raise HTTPException(status_code=422, detail=f"Invalid crawl URL: {url_reason}")

    # Detect platform
    platform = "unknown"
    if "1688.com" in source_url:
        platform = "1688"
    elif "taobao.com" in source_url or "tmall.com" in source_url:
        platform = "taobao"

    crawl_run = CrawlRun(
        task_id=task_id,
        source_url=source_url,
        source_platform=platform,
        status="pending",
    )
    db.add(crawl_run)
    db.commit()
    db.refresh(crawl_run)

    # Try to enqueue via ARQ if Redis is available
    if app_settings.redis_url:
        try:
            from arq import create_pool
            from arq.connections import RedisSettings

            redis = await create_pool(RedisSettings.from_dsn(app_settings.redis_url))
            await redis.enqueue_job("crawl_competitor_page", crawl_run.id)
            await redis.close()
            logger.info("Crawl job enqueued for crawl_run %d", crawl_run.id)
        except Exception:
            logger.exception("Failed to enqueue crawl job, running inline")
            await _run_crawl_inline(crawl_run.id)
    else:
        logger.warning("Redis not configured, running crawl inline (blocking)")
        await _run_crawl_inline(crawl_run.id)

    db.refresh(crawl_run)
    return CrawlRunRead.model_validate(crawl_run)


@router.get("/{task_id}/crawl-status", response_model=list[CrawlRunRead])
def get_crawl_status(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CrawlRunRead]:
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return [CrawlRunRead.model_validate(cr) for cr in task.crawl_runs]


async def _run_crawl_inline(crawl_run_id: int) -> None:
    """Fallback: run crawl directly without ARQ."""
    from ..crawler.worker import crawl_competitor_page
    await crawl_competitor_page({}, crawl_run_id)
