#!/usr/bin/env python3
"""Trigger a fetch job for a source or specific lot."""
import argparse
import asyncio
import sys
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StubSettings:
    """Stub settings loader for when backend modules aren't available."""
    def __init__(self):
        self.auctionet_base_url = "https://auctionet.com"
        self.requests_per_minute = 20
        self.delay_between_requests_seconds = 3


class StubFetcher:
    """Stub fetcher implementation for development."""

    def __init__(self, settings):
        self.settings = settings
        self.logger = logging.getLogger(__name__)

    async def fetch_listing_page(self, page: int, category: str = "furniture"):
        """Stub: fetch a listing page."""
        self.logger.info(f"[STUB] Fetching listing page {page} from {self.settings.auctionet_base_url}")
        self.logger.info(f"[STUB] Category: {category}")
        # Return empty list to avoid errors
        return []

    async def fetch_lot_detail(self, url: str):
        """Stub: fetch a single lot detail."""
        self.logger.info(f"[STUB] Fetching lot detail from {url}")
        return {"content_hash": "stub_hash_0000"}

    async def close(self):
        """Cleanup."""
        pass


def load_settings():
    """Load settings from config or return stub."""
    try:
        from backend.config import load_settings as real_load
        return real_load()
    except (ImportError, ModuleNotFoundError):
        logger.warning("backend.config not available, using stub settings")
        return StubSettings()


def get_fetcher(settings):
    """Get fetcher instance."""
    try:
        from backend.ingestion.fetcher import AuctionetFetcher
        return AuctionetFetcher(settings)
    except (ImportError, ModuleNotFoundError):
        logger.warning("backend.ingestion.fetcher not available, using stub fetcher")
        return StubFetcher(settings)


async def fetch_source(source_name: str, category: str = "furniture", max_pages: int = 5):
    """Broad crawl of a source."""
    settings = load_settings()
    fetcher = get_fetcher(settings)

    logger.info(f"Starting broad crawl of {source_name}, category={category}, max_pages={max_pages}")

    lot_urls = []
    for page in range(1, max_pages + 1):
        urls = await fetcher.fetch_listing_page(page, category=category)
        if not urls:
            logger.info(f"Page {page}: no lots found, stopping")
            break
        lot_urls.extend(urls)
        logger.info(f"Page {page}: found {len(urls)} lots")

    logger.info(f"Total lots found: {len(lot_urls)}")

    for url in lot_urls:
        try:
            result = await fetcher.fetch_lot_detail(url)
            content_hash = result.get('content_hash', 'unknown')[:12]
            logger.info(f"Fetched: {url} -> {content_hash}")
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")

    await fetcher.close()
    logger.info("Broad crawl complete")


async def fetch_lot(lot_url: str):
    """Fetch a single lot."""
    settings = load_settings()
    fetcher = get_fetcher(settings)

    logger.info(f"Fetching single lot: {lot_url}")
    result = await fetcher.fetch_lot_detail(lot_url)
    content_hash = result.get('content_hash', 'unknown')

    logger.info(f"Fetched: {lot_url}")
    logger.info(f"Content hash: {content_hash}")

    await fetcher.close()


def main():
    parser = argparse.ArgumentParser(
        description="Fetch auction lots from configured sources"
    )
    subparsers = parser.add_subparsers(dest="command")

    source_parser = subparsers.add_parser(
        "source",
        help="Broad crawl a source"
    )
    source_parser.add_argument("name", help="Source name (e.g., auctionet)")
    source_parser.add_argument(
        "--category",
        default="furniture",
        help="Category to fetch (default: furniture)"
    )
    source_parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="Maximum pages to fetch (default: 5)"
    )

    lot_parser = subparsers.add_parser(
        "lot",
        help="Fetch a single lot by URL"
    )
    lot_parser.add_argument("url", help="Lot URL to fetch")

    args = parser.parse_args()

    if args.command == "source":
        asyncio.run(fetch_source(args.name, args.category, args.max_pages))
    elif args.command == "lot":
        asyncio.run(fetch_lot(args.url))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
