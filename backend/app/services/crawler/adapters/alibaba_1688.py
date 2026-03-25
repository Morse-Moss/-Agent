"""1688 (Alibaba) crawl adapter — official API first, Playwright fallback."""
from __future__ import annotations

import logging
import re

from .base import BaseCrawlAdapter, CrawlResult

logger = logging.getLogger(__name__)


class Alibaba1688Adapter(BaseCrawlAdapter):
    platform = "1688"

    @classmethod
    def can_handle(cls, url: str) -> bool:
        return bool(re.search(r"(1688\.com|detail\.1688\.com)", url))

    async def crawl(self, url: str) -> CrawlResult:
        # Try official API first
        result = await self._try_official_api(url)
        if result.success:
            return result

        # Fallback to Playwright
        logger.info("1688 official API unavailable, falling back to Playwright for %s", url)
        return await self._crawl_with_playwright(url)

    async def _try_official_api(self, url: str) -> CrawlResult:
        """Try 1688 open platform API. Returns unsuccessful result if not configured."""
        # TODO: Implement when API credentials are available
        # 1688 open API: https://open.1688.com/
        return CrawlResult(error="1688 official API not configured", success=False)

    async def _crawl_with_playwright(self, url: str) -> CrawlResult:
        """Crawl 1688 product page using Playwright."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return CrawlResult(error="Playwright not installed", success=False)

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=30000)

                # Extract product name
                product_name = ""
                title_el = await page.query_selector("h1.title-text, .mod-detail-title h1")
                if title_el:
                    product_name = (await title_el.inner_text()).strip()

                # Extract product images
                image_urls: list[str] = []
                img_elements = await page.query_selector_all(
                    ".detail-gallery-img img, .tab-pane img, .detail-gallery img"
                )
                for img in img_elements:
                    src = await img.get_attribute("src") or await img.get_attribute("data-src") or ""
                    if src and not src.startswith("data:"):
                        if src.startswith("//"):
                            src = "https:" + src
                        image_urls.append(src)

                # Extract price
                price = ""
                price_el = await page.query_selector(".price-text, .price-original-text")
                if price_el:
                    price = (await price_el.inner_text()).strip()

                await browser.close()

                if not image_urls:
                    return CrawlResult(
                        product_name=product_name,
                        error="No images found on page",
                        success=False,
                    )

                return CrawlResult(
                    product_name=product_name,
                    image_urls=image_urls[:20],  # cap at 20
                    price=price,
                    success=True,
                )
        except Exception as exc:
            logger.exception("Playwright crawl failed for %s", url)
            return CrawlResult(error=str(exc), success=False)
