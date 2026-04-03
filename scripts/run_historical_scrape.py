#!/usr/bin/env python3
"""Run a broader historical scrape and import to DB."""
import asyncio
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

from backend.database import SessionLocal, init_db
from backend.ingestion.auctionet_historical import fetch_ended_auctions, to_historical_records, import_to_db


async def main():
    init_db()
    db = SessionLocal()

    try:
        # Broad sweep: 10 pages
        logger.info("Starting broad sweep (10 pages)...")
        items = await fetch_ended_auctions(query="", max_pages=10)
        records = to_historical_records(items)

        # Quick stats before import
        with_date = sum(1 for r in records if r['auction_end_date'])
        with_bids = sum(1 for r in records if r['bid_count'] is not None)
        sold = sum(1 for r in records if r['was_sold'] == 1)
        unsold = sum(1 for r in records if r['was_sold'] == 0)

        logger.info(f"Broad sweep: {len(items)} items -> {len(records)} records")
        logger.info(f"  With dates: {with_date}, With bids: {with_bids}")
        logger.info(f"  Sold: {sold}, Unsold: {unsold}")

        inserted = import_to_db(records, db)
        logger.info(f"  Imported: {inserted} new records")

    finally:
        db.close()


asyncio.run(main())
