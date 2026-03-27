"""Image downloader for auction lots."""

import asyncio
import logging
from pathlib import Path
from typing import Optional

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)


class ImageDownloader:
    """Downloads and stores images for auction lots."""

    def __init__(self, rate_limit_requests: int = 5, rate_limit_period: int = 60):
        """Initialize image downloader.

        Args:
            rate_limit_requests: Number of requests allowed
            rate_limit_period: Time period in seconds for rate limit
        """
        self.rate_limit_requests = rate_limit_requests
        self.rate_limit_period = rate_limit_period
        self.client = httpx.AsyncClient(timeout=30.0)
        self.request_times = []

    async def _apply_rate_limit(self):
        """Apply rate limiting to requests."""
        from datetime import datetime

        now = datetime.utcnow().timestamp()
        self.request_times = [t for t in self.request_times if now - t < self.rate_limit_period]

        if len(self.request_times) >= self.rate_limit_requests:
            sleep_time = self.rate_limit_period - (now - self.request_times[0])
            if sleep_time > 0:
                logger.info(f"Image download rate limit hit, sleeping for {sleep_time:.1f}s")
                await asyncio.sleep(sleep_time)
            self.request_times = []

        self.request_times.append(datetime.utcnow().timestamp())

    async def download_image(
        self,
        image_url: str,
        source_name: str,
        lot_id: int,
        sort_order: int = 0,
    ) -> Optional[str]:
        """Download a single image for a lot.

        Args:
            image_url: URL of the image
            source_name: Name of the auction source
            lot_id: ID of the lot
            sort_order: Order of the image

        Returns:
            Local path to the downloaded image, or None if failed
        """
        await self._apply_rate_limit()

        try:
            # Create directory for lot images
            images_dir = settings.images_dir / source_name / str(lot_id)
            images_dir.mkdir(parents=True, exist_ok=True)

            # Download image
            logger.info(f"Downloading image: {image_url}")
            response = await self.client.get(image_url)

            if response.status_code != 200:
                logger.warning(f"Failed to download image {image_url}: HTTP {response.status_code}")
                return None

            # Determine file extension from content-type or URL
            content_type = response.headers.get("content-type", "image/jpeg")
            ext = self._get_extension(content_type, image_url)

            # Save image
            filename = f"{sort_order:03d}{ext}"
            local_path = images_dir / filename
            local_path.write_bytes(response.content)

            logger.info(f"Saved image to {local_path}")
            return str(local_path)

        except Exception as e:
            logger.error(f"Error downloading image {image_url}: {e}")
            return None

    def _get_extension(self, content_type: str, url: str) -> str:
        """Get file extension from content type or URL.

        Args:
            content_type: Content-Type header value
            url: Image URL

        Returns:
            File extension including the dot
        """
        # Map content types to extensions
        type_map = {
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "image/webp": ".webp",
        }

        # Try content type first
        ext = type_map.get(content_type.lower(), None)
        if ext:
            return ext

        # Try URL extension
        if "." in url:
            potential_ext = "." + url.split(".")[-1].split("?")[0].lower()
            if potential_ext in [".jpg", ".png", ".gif", ".webp"]:
                return potential_ext

        # Default to jpg
        return ".jpg"

    async def download_images(
        self,
        image_urls: list[str],
        source_name: str,
        lot_id: int,
    ) -> list[tuple[str, Optional[str]]]:
        """Download multiple images for a lot.

        Args:
            image_urls: List of image URLs
            source_name: Name of the auction source
            lot_id: ID of the lot

        Returns:
            List of (url, local_path) tuples
        """
        tasks = [
            self.download_image(url, source_name, lot_id, i)
            for i, url in enumerate(image_urls)
        ]
        paths = await asyncio.gather(*tasks, return_exceptions=True)

        return [
            (url, path if isinstance(path, str) else None)
            for url, path in zip(image_urls, paths)
        ]

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
