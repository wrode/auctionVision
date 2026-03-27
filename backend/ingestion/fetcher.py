"""Fetcher classes for downloading auction data."""

import asyncio
import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx

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
        self.client = httpx.AsyncClient(timeout=30.0)

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
        """Close HTTP client."""
        await self.client.aclose()


class AuctionetFetcher(BaseFetcher):
    """Fetcher for Auctionet.com."""

    def __init__(self):
        """Initialize Auctionet fetcher."""
        super().__init__(
            source_name="auctionet",
            rate_limit_requests=settings.auctionet_rate_limit_requests,
            rate_limit_period=settings.auctionet_rate_limit_period,
        )
        self.base_url = settings.auctionet_base_url
        self.request_times = []

    async def _apply_rate_limit(self):
        """Apply rate limiting to requests."""
        now = datetime.utcnow().timestamp()
        # Remove old timestamps outside the window
        self.request_times = [t for t in self.request_times if now - t < self.rate_limit_period]

        # Wait if necessary
        if len(self.request_times) >= self.rate_limit_requests:
            sleep_time = self.rate_limit_period - (now - self.request_times[0])
            if sleep_time > 0:
                logger.info(f"Rate limit hit, sleeping for {sleep_time:.1f}s")
                await asyncio.sleep(sleep_time)
            self.request_times = []

        self.request_times.append(datetime.utcnow().timestamp())

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
        await self._apply_rate_limit()

        # Stub implementation - would construct actual search URL
        logger.info(f"Fetching listing page {page_num} for category {category}")
        # In real implementation, would:
        # 1. Construct URL: https://auctionet.com/search?category=furniture&page=1
        # 2. Fetch and parse HTML
        # 3. Extract lot URLs and IDs
        # 4. Return as list of dicts

        return []

    async def fetch_lot_detail(self, lot_url: str) -> dict[str, Any]:
        """Fetch a single lot detail page from Auctionet.

        Args:
            lot_url: URL of the lot

        Returns:
            Dictionary with raw_html, http_status, content_hash, raw_html_path
        """
        await self._apply_rate_limit()

        logger.info(f"Fetching lot detail: {lot_url}")

        try:
            response = await self.client.get(lot_url)
            content = response.content
            content_hash = self._compute_content_hash(content)

            # Extract lot ID from URL (stub - real extraction would be more sophisticated)
            lot_id = "unknown"
            if "/lot/" in lot_url:
                lot_id = lot_url.split("/lot/")[-1].split("/")[0]

            # Save raw HTML to snapshots directory
            date_str = datetime.utcnow().strftime("%Y-%m-%d")
            snapshot_dir = settings.snapshots_dir / "auctionet" / date_str
            snapshot_dir.mkdir(parents=True, exist_ok=True)

            raw_html_path = snapshot_dir / f"{lot_id}_{content_hash[:8]}.html"
            raw_html_path.write_bytes(content)

            logger.info(f"Saved HTML to {raw_html_path}")

            return {
                "http_status": response.status_code,
                "content_hash": content_hash,
                "raw_html": content.decode("utf-8", errors="ignore"),
                "raw_html_path": str(raw_html_path),
                "success": response.status_code == 200,
                "error_message": None if response.status_code == 200 else f"HTTP {response.status_code}",
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
