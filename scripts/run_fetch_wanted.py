#!/usr/bin/env python3
"""Fetch Finn.no 'Ønskes kjøpt' wanted listings and store all of them.

Usage:
    python scripts/run_fetch_wanted.py           # fetch all categories
    python scripts/run_fetch_wanted.py --dry-run  # preview without saving to DB
"""
import asyncio
import sys
import logging
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def fetch_wanted(dry_run: bool = False):
    from backend.database import SessionLocal, init_db
    from backend.ingestion.finn_wanted import FinnWantedFetcher
    from backend.models import WantedListing

    init_db()
    db = SessionLocal()
    fetcher = FinnWantedFetcher()

    try:
        all_listings = await fetcher.fetch_all_categories()

        if dry_run:
            high = [l for l in all_listings if l.get("is_high_value")]
            logger.info(
                f"DRY RUN: {len(all_listings)} total wanted listings, "
                f"{len(high)} high-value:"
            )
            for listing in high:
                price_str = f"{listing['offered_price']} NOK" if listing.get("offered_price") else "no price"
                logger.info(
                    f"  [{listing['match_reason']}] {listing['title'][:80]} "
                    f"({price_str}) - {listing.get('buyer_location', '?')}"
                )
            return

        # Upsert into database
        created = 0
        updated = 0
        for listing in all_listings:
            existing = db.query(WantedListing).filter(
                WantedListing.finn_id == listing["finn_id"]
            ).first()

            if existing:
                existing.title = listing["title"]
                existing.offered_price = listing.get("offered_price")
                existing.brand = listing.get("brand")
                existing.buyer_location = listing.get("buyer_location")
                existing.image_urls = listing.get("image_urls")
                existing.published_text = listing.get("published_text")
                existing.is_high_value = 1 if listing.get("is_high_value") else 0
                existing.match_reason = listing.get("match_reason")
                existing.last_seen_at = datetime.now(timezone.utc)
                existing.status = "active"
                updated += 1
            else:
                new_listing = WantedListing(
                    finn_id=listing["finn_id"],
                    url=listing["url"],
                    title=listing["title"],
                    offered_price=listing.get("offered_price"),
                    currency="NOK",
                    brand=listing.get("brand"),
                    category=listing.get("category"),
                    buyer_location=listing.get("buyer_location"),
                    image_urls=listing.get("image_urls"),
                    published_text=listing.get("published_text"),
                    status="active",
                    is_high_value=1 if listing.get("is_high_value") else 0,
                    match_reason=listing.get("match_reason"),
                    first_seen_at=datetime.now(timezone.utc),
                    last_seen_at=datetime.now(timezone.utc),
                )
                db.add(new_listing)
                created += 1

        db.commit()
        total = db.query(WantedListing).count()
        high_total = db.query(WantedListing).filter(WantedListing.is_high_value == 1).count()
        logger.info(
            f"Done: {created} new, {updated} updated. "
            f"Total wanted: {total}, high-value: {high_total}"
        )

    finally:
        await fetcher.close()
        db.close()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(fetch_wanted(dry_run=dry_run))
