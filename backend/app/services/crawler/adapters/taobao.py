"""Taobao / Tmall crawl adapter — official API first, Playwright fallback."""
from __future__ import annotations

import logging
import re

from .base import BaseCrawlAdapter, CrawlResult

logger = logging.getLogger(__name__)


class TaobaoAdapter(BaseCrawlAdapter):
    platform = "taobao"

    @classmethod
    def can_handle(cls, url: str) -> bool:
        return bool(re.search(r"(taobao\.com|tmall\.com|item\.taobao|detail\.tmall)", url))

    async def crawl(self, url: str) -> CrawlResult:
        result = await self._try_official_api(url)
        if result.success:
            return result

        logger.info("Taobao official API unavailable, falling back to Playwright for %s", url)
        return await self._crawl_with_playwright(url)

    async def _try_official_api(self, url: str) -> CrawlResult:
        """Try Taobao open platform API."""
        # TODO: Implement when API credentials are available
        return CrawlResult(error="Taobao official API not configured", success=False)

    async def _crawl_with_playwright(self, url: str) -> CrawlResult:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return CrawlResult(error="Playwright not installed", success=False)

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=30000)

                product_name = ""
                title_el = await page.query_selector(
                    "h1[class*='title'], .tb-main-title, .ItemHeader--mainTitle"
                )
                if title_el:
                    product_name = (await title_el.inner_text()).strip()

                image_urls: list[str] = []
                img_elements = await page.query_selector_all(
                    ".tb-thumb img, .PicGallery--thumbnails img, img[class*='thumbnail']"
                )
                for img in img_elements:
                    src = await img.get_attribute("src") or await img.get_attribute("data-src") or ""
                    if src and not src.startswith("data:"):
                        if src.startswith("//"):
                            src = "https:" + src
                        # Get full-size image
                        src = re.sub(r"_\d+x\d+\.\w+$", "", src)
                        image_urls.append(src)

                price = ""
                price_el = await page.query_selector(
                    ".tb-rmb-num, .Price--currentPrice, span[class*='price']"
                )
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
                    image_urls=image_urls[:20],
                    price=price,
                    success=True,
                )
        except Exception as exc:
            logger.exception("Playwright crawl failed for %s", url)
            return CrawlResult(error=str(exc), success=False)
