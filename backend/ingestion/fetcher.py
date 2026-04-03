"""Fetcher classes for downloading auction data."""

import asyncio
import hashlib
import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from playwright.async_api import async_playwright

from backend.config import settings

logger = logging.getLogger(__name__)


class BaseFetcher(ABC):
    """Abstract base fetcher class."""

    def __init__(self, source_name: str, rate_limit_requests: int = 10, rate_limit_period: int = 60):
        """Initialize fetcher.

        Args:
            source_name: Name of the auction source
            rate_limit_requests: Number of requests allowed
            rate_limit_period: Time period in seconds for rate limit
        """
        self.source_name = source_name
        self.rate_limit_requests = rate_limit_requests
        self.rate_limit_period = rate_limit_period

    @abstractmethod
    async def fetch_listing_page(self, page_num: int, **kwargs) -> list[dict[str, Any]]:
        """Fetch a listing page.

        Args:
            page_num: Page number
            **kwargs: Additional arguments

        Returns:
            List of lot metadata with url and external_id
        """
        pass

    @abstractmethod
    async def fetch_lot_detail(self, lot_url: str) -> dict[str, Any]:
        """Fetch a single lot detail page.

        Args:
            lot_url: URL of the lot

        Returns:
            Dictionary with raw_html, http_status, content_hash, etc.
        """
        pass

    def _compute_content_hash(self, content: bytes) -> str:
        """Compute SHA256 hash of content."""
        return hashlib.sha256(content).hexdigest()

    async def close(self):
        """Close any resources."""
        pass


class AuctionetFetcher(BaseFetcher):
    """Fetcher for Auctionet.com using Playwright."""

    def __init__(self):
        """Initialize Auctionet fetcher."""
        super().__init__(
            source_name="auctionet",
            rate_limit_requests=settings.auctionet_rate_limit_requests,
            rate_limit_period=settings.auctionet_rate_limit_period,
        )
        self.base_url = settings.auctionet_base_url
        self.browser = None
        self.context = None
        self.page = None

    async def _init_browser(self):
        """Initialize Playwright browser and page."""
        if self.browser is None:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=True)
            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()
            logger.info("Initialized Playwright browser")

    async def _apply_rate_limit(self):
        """Apply simple rate limiting between requests."""
        await asyncio.sleep(2)

    async def fetch_listing_page(
        self,
        page_num: int = 1,
        category: str = "furniture",
    ) -> list[dict[str, Any]]:
        """Fetch a listing page from Auctionet.

        Args:
            page_num: Page number to fetch
            category: Category to filter (e.g., "furniture")

        Returns:
            List of lot metadata with external_lot_id and lot_url
        """
        await self._init_browser()
        await self._apply_rate_limit()

        url = f"{self.base_url}/en/search?q={category}&page={page_num}"
        logger.info(f"Fetching listing page {page_num} for category {category}: {url}")

        try:
            await self.page.goto(url, wait_until="networkidle")
            html = await self.page.content()

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")

            lots = []
            seen_ids = set()

            # Extract lot links matching /en/{id}-{slug} pattern
            for link in soup.find_all("a", href=re.compile(r"/en/\d+-")):
                href = link.get("href")
                if not href:
                    continue

                # Extract lot ID using regex: /en/(\d+)-
                match = re.search(r"/en/(\d+)-", href)
                if not match:
                    continue

                lot_id = match.group(1)
                if lot_id in seen_ids:
                    continue

                seen_ids.add(lot_id)

                # Normalize URL to absolute
                if href.startswith("/"):
                    lot_url = f"{self.base_url}{href}"
                else:
                    lot_url = href

                # Try to find thumbnail image near this link
                thumb_url = None
                card = link.parent
                for _ in range(3):
                    if card and card.parent:
                        card = card.parent
                if card:
                    img = card.find("img")
                    if img:
                        thumb_url = img.get("src") or img.get("data-src")

                lots.append({
                    "external_lot_id": lot_id,
                    "lot_url": lot_url,
                    "thumbnail_url": thumb_url,
                })
                logger.debug(f"Found lot: {lot_id} -> {lot_url}")

            logger.info(f"Extracted {len(lots)} lots from page {page_num}")
            return lots

        except Exception as e:
            logger.error(f"Error fetching listing page {page_num}: {e}")
            return []

    async def fetch_lot_detail(self, lot_url: str) -> dict[str, Any]:
        """Fetch a single lot detail page from Auctionet.

        Args:
            lot_url: URL of the lot

        Returns:
            Dictionary with raw_html, http_status, content_hash, raw_html_path
        """
        await self._init_browser()
        await self._apply_rate_limit()

        logger.info(f"Fetching lot detail: {lot_url}")

        try:
            await self.page.goto(lot_url, wait_until="networkidle")
            html = await self.page.content()
            content = html.encode("utf-8")
            content_hash = self._compute_content_hash(content)

            # Extract lot ID from URL using regex: /en/(\d+)-
            lot_id = "unknown"
            match = re.search(r"/en/(\d+)-", lot_url)
            if match:
                lot_id = match.group(1)

            # Save raw HTML to snapshots directory
            date_str = datetime.utcnow().strftime("%Y-%m-%d")
            snapshot_dir = settings.snapshots_dir / "auctionet" / date_str
            snapshot_dir.mkdir(parents=True, exist_ok=True)

            raw_html_path = snapshot_dir / f"{lot_id}_{content_hash[:8]}.html"
            raw_html_path.write_bytes(content)

            logger.info(f"Saved HTML to {raw_html_path}")

            return {
                "http_status": 200,
                "content_hash": content_hash,
                "raw_html": html,
                "raw_html_path": str(raw_html_path),
                "success": True,
                "error_message": None,
            }

        except Exception as e:
            logger.error(f"Error fetching lot detail {lot_url}: {e}")
            return {
                "http_status": None,
                "content_hash": None,
                "raw_html": None,
                "raw_html_path": None,
                "success": False,
                "error_message": str(e),
            }

    async def close(self):
        """Close Playwright browser."""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        logger.info("Closed Playwright browser")
