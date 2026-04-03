#!/usr/bin/env python3
"""Trigger a fetch job for a source or specific lot."""
import argparse
import asyncio
import sys
import logging
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def fetch_source(source_name: str, category: str = "furniture", max_pages: int = 2):
    """Broad crawl of a source with database integration."""
    # Import backend modules
    from backend.config import settings
    from backend.database import SessionLocal, init_db
    from backend.ingestion.fetcher import AuctionetFetcher
    from backend.models import Source, Lot, LotFetch, LotImage

    # Initialize database
    init_db()
    db = SessionLocal()

    try:
        # Initialize fetcher
        fetcher = AuctionetFetcher()
        logger.info(f"Starting broad crawl of {source_name}, category={category}, max_pages={max_pages}")

        # Create or get Source record
        source = db.query(Source).filter(Source.name == source_name).first()
        if not source:
            source = Source(
                name=source_name,
                base_url=settings.auctionet_base_url,
                parser_name="auctionet_v2",
            )
            db.add(source)
            db.commit()
            logger.info(f"Created new Source: {source_name}")
        else:
            logger.info(f"Using existing Source: {source_name}")

        # Fetch listings and discover lots
        all_lots = []
        for page in range(1, max_pages + 1):
            listing_data = await fetcher.fetch_listing_page(page, category=category)
            if not listing_data:
                logger.info(f"Page {page}: no lots found, stopping")
                break

            logger.info(f"Page {page}: found {len(listing_data)} lots")
            all_lots.extend(listing_data)

        logger.info(f"Total lots discovered: {len(all_lots)}")

        # For each lot, fetch detail and save records
        for lot_data in all_lots:
            external_lot_id = lot_data.get("external_lot_id")
            lot_url = lot_data.get("lot_url")

            if not lot_url:
                logger.warning(f"Skipping lot with no URL: {lot_data}")
                continue

            logger.info(f"Processing lot {external_lot_id}: {lot_url}")

            # Create or get Lot record
            lot = db.query(Lot).filter(
                Lot.source_id == source.id,
                Lot.external_lot_id == external_lot_id,
            ).first()

            if not lot:
                lot = Lot(
                    source_id=source.id,
                    external_lot_id=external_lot_id,
                    lot_url=lot_url,
                )
                db.add(lot)
                db.commit()
                logger.info(f"Created new Lot: {external_lot_id}")
            else:
                logger.info(f"Using existing Lot: {external_lot_id}")

            # Fetch lot detail
            try:
                fetch_result = await fetcher.fetch_lot_detail(lot_url)

                if not fetch_result.get("success"):
                    logger.warning(f"Failed to fetch lot {external_lot_id}: {fetch_result.get('error_message')}")
                    continue

                # Create LotFetch record
                lot_fetch = LotFetch(
                    lot_id=lot.id,
                    fetched_at=datetime.utcnow(),
                    fetch_type="full",
                    http_status=fetch_result.get("http_status"),
                    content_hash=fetch_result.get("content_hash"),
                    raw_html_path=fetch_result.get("raw_html_path"),
                    success=fetch_result.get("success", 0),
                    error_message=fetch_result.get("error_message"),
                )
                db.add(lot_fetch)
                db.commit()
                logger.info(f"Created LotFetch: {external_lot_id}")

                # Update lot's last_fetched_at
                lot.last_fetched_at = datetime.utcnow()
                db.commit()

            except Exception as e:
                logger.error(f"Error fetching lot {external_lot_id}: {e}")
                continue

        logger.info("Broad crawl complete")

    finally:
        await fetcher.close()
        db.close()


async def fetch_lot(lot_url: str):
    """Fetch a single lot by URL."""
    from backend.config import settings
    from backend.database import SessionLocal, init_db
    from backend.ingestion.fetcher import AuctionetFetcher
    from backend.models import Source, Lot, LotFetch

    init_db()
    db = SessionLocal()

    try:
        fetcher = AuctionetFetcher()
        logger.info(f"Fetching single lot: {lot_url}")

        # Get or create source
        source = db.query(Source).filter(Source.name == "auctionet").first()
        if not source:
            source = Source(
                name="auctionet",
                base_url=settings.auctionet_base_url,
                parser_name="auctionet_v2",
            )
            db.add(source)
            db.commit()

        # Extract lot ID from URL using regex: /en/(\d+)-
        import re
        lot_id = "unknown"
        match = re.search(r"/en/(\d+)-", lot_url)
        if match:
            lot_id = match.group(1)

        # Get or create lot
        lot = db.query(Lot).filter(
            Lot.source_id == source.id,
            Lot.external_lot_id == lot_id,
        ).first()

        if not lot:
            lot = Lot(
                source_id=source.id,
                external_lot_id=lot_id,
                lot_url=lot_url,
            )
            db.add(lot)
            db.commit()

        # Fetch and save
        fetch_result = await fetcher.fetch_lot_detail(lot_url)

        lot_fetch = LotFetch(
            lot_id=lot.id,
            fetched_at=datetime.utcnow(),
            fetch_type="full",
            http_status=fetch_result.get("http_status"),
            content_hash=fetch_result.get("content_hash"),
            raw_html_path=fetch_result.get("raw_html_path"),
            success=fetch_result.get("success", 0),
            error_message=fetch_result.get("error_message"),
        )
        db.add(lot_fetch)
        db.commit()

        lot.last_fetched_at = datetime.utcnow()
        db.commit()

        logger.info(f"Fetched lot {lot_id}, saved to {fetch_result.get('raw_html_path')}")

    finally:
        await fetcher.close()
        db.close()


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
        default=2,
        help="Maximum pages to fetch (default: 2)"
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
