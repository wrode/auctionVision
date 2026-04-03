#!/usr/bin/env python3
"""Fetch Finn.no for-sale market data by designer/brand and store snapshots.

Usage:
    python scripts/run_fetch_forsale.py           # fetch and save to DB
    python scripts/run_fetch_forsale.py --dry-run  # preview without saving
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


async def fetch_forsale(dry_run: bool = False):
    from backend.database import SessionLocal, init_db
    from backend.ingestion.finn_forsale import FinnForSaleScraper
    from backend.models import FinnForSaleListing, FinnMarketData

    init_db()
    db = SessionLocal()
    scraper = FinnForSaleScraper()

    try:
        market_data, raw_listings = await scraper.fetch_market_data()

        if dry_run:
            logger.info(f"DRY RUN: {len(market_data)} market data snapshots:")
            for data in market_data:
                logger.info(
                    f"  [{data['query_type']}] {data['query_value']}: "
                    f"{data['listing_count']} listings, "
                    f"median {data.get('median_price_nok', 'N/A')} NOK, "
                    f"range {data.get('min_price_nok', '?')}-{data.get('max_price_nok', '?')} NOK"
                )
            logger.info(f"DRY RUN: {len(raw_listings)} individual listings would be tracked")
            return

        # --- Save aggregated stats (existing logic) ---
        created = 0
        updated = 0
        for data in market_data:
            existing = db.query(FinnMarketData).filter(
                FinnMarketData.query_type == data["query_type"],
                FinnMarketData.query_value == data["query_value"],
            ).first()

            if existing:
                for key, val in data.items():
                    if key != "id":
                        setattr(existing, key, val)
                existing.scraped_at = datetime.now(timezone.utc)
                updated += 1
            else:
                db.add(FinnMarketData(**data))
                created += 1

        db.commit()
        total = db.query(FinnMarketData).count()
        logger.info(
            f"Market data: {created} new, {updated} updated. "
            f"Total market data rows: {total}"
        )

        # --- Save individual listings + detect churn ---
        seen_finn_ids = set()
        listings_created = 0
        listings_updated = 0

        for listing in raw_listings:
            seen_finn_ids.add((listing["finn_id"], listing["search_query"]))

            existing = db.query(FinnForSaleListing).filter(
                FinnForSaleListing.finn_id == listing["finn_id"],
            ).first()

            if existing:
                existing.last_seen_at = datetime.now(timezone.utc)
                existing.status = "active"  # re-appeared or still there
                existing.disappeared_at = None
                # Update price if changed
                if listing.get("price_nok") and listing["price_nok"] != existing.price_nok:
                    existing.price_nok = listing["price_nok"]
                listings_updated += 1
            else:
                db.add(FinnForSaleListing(**listing))
                listings_created += 1

        # Mark disappeared listings: were active but not seen in the current query scope
        queries_run = set(l["search_query"] for l in raw_listings)
        disappeared_count = 0
        for query in queries_run:
            query_finn_ids = {fid for fid, q in seen_finn_ids if q == query}
            stale_filter = db.query(FinnForSaleListing).filter(
                FinnForSaleListing.search_query == query,
                FinnForSaleListing.status == "active",
            )
            if query_finn_ids:
                stale_filter = stale_filter.filter(
                    ~FinnForSaleListing.finn_id.in_(query_finn_ids),
                )
            stale = stale_filter.all()
            for s in stale:
                s.status = "disappeared"
                s.disappeared_at = datetime.now(timezone.utc)
                disappeared_count += 1

        db.commit()

        # Log churn stats
        total_listings = db.query(FinnForSaleListing).count()
        active = db.query(FinnForSaleListing).filter(
            FinnForSaleListing.status == "active"
        ).count()
        disappeared = db.query(FinnForSaleListing).filter(
            FinnForSaleListing.status == "disappeared"
        ).count()
        logger.info(
            f"Listings: {listings_created} new, {listings_updated} updated, "
            f"{disappeared_count} newly disappeared"
        )
        logger.info(
            f"Listings tracked: {total_listings} total, "
            f"{active} active, {disappeared} disappeared"
        )

    finally:
        await scraper.close()
        db.close()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(fetch_forsale(dry_run=dry_run))
