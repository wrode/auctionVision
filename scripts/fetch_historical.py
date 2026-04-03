#!/usr/bin/env python3
"""Fetch historical hammer prices from Auctionet ended auctions.

Usage:
    # Broad sweep of ended furniture auctions
    python scripts/fetch_historical.py broad --pages 10

    # Targeted search for a specific designer
    python scripts/fetch_historical.py designer "Hans Wegner" --pages 5

    # Scrape all priority designers from config
    python scripts/fetch_historical.py priority

    # Fetch full detail for lots missing data (enriches listing-page data)
    python scripts/fetch_historical.py enrich --limit 50
"""
import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def broad_sweep(max_pages: int = 10):
    """Broad sweep of ended furniture auctions."""
    from backend.config import load_yaml_config
    from backend.database import SessionLocal, init_db
    from backend.ingestion.auctionet_historical import (
        fetch_ended_auctions,
        to_historical_records,
        import_to_db,
    )

    init_db()

    logger.info(f"Starting broad sweep, max_pages={max_pages}")
    items = await fetch_ended_auctions(query="", max_pages=max_pages)
    logger.info(f"Fetched {len(items)} ended lots")

    # Save raw data
    cache_path = Path("data/historical_auctionet_broad.json")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(items, default=str, indent=2))
    logger.info(f"Cached raw data to {cache_path}")

    records = to_historical_records(items)
    logger.info(f"Converted to {len(records)} records")

    db = SessionLocal()
    try:
        inserted = import_to_db(records, db)
        logger.info(f"Done: {inserted} new records imported")
    finally:
        db.close()


async def designer_search(designer: str, max_pages: int = 5):
    """Search ended auctions for a specific designer."""
    from backend.database import SessionLocal, init_db
    from backend.ingestion.auctionet_historical import (
        fetch_ended_auctions,
        to_historical_records,
        import_to_db,
    )

    init_db()

    logger.info(f"Searching ended auctions for: {designer}")
    items = await fetch_ended_auctions(query=designer, max_pages=max_pages)
    logger.info(f"Fetched {len(items)} ended lots for '{designer}'")

    # Save raw data
    safe_name = designer.lower().replace(" ", "_")
    cache_path = Path(f"data/historical_auctionet_{safe_name}.json")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(items, default=str, indent=2))

    records = to_historical_records(items)
    logger.info(f"Converted to {len(records)} records")

    db = SessionLocal()
    try:
        inserted = import_to_db(records, db)
        logger.info(f"Done: {inserted} new records for '{designer}'")
    finally:
        db.close()


async def priority_designers(max_pages: int = 5):
    """Scrape all priority designers from config."""
    from backend.config import load_yaml_config

    config = load_yaml_config("historical.yaml")
    designers = config.get("scraper", {}).get("auctionet", {}).get("priority_designers", [])

    if not designers:
        logger.error("No priority_designers found in config/historical.yaml")
        return

    logger.info(f"Scraping {len(designers)} priority designers")
    for i, designer in enumerate(designers, 1):
        logger.info(f"[{i}/{len(designers)}] {designer}")
        await designer_search(designer, max_pages=max_pages)


async def enrich_details(limit: int = 50):
    """Fetch full detail for lots missing designer/description data."""
    from backend.database import SessionLocal, init_db
    from backend.models import HistoricalHammer
    from backend.ingestion.auctionet_historical import fetch_ended_lot_detail

    init_db()
    db = SessionLocal()

    try:
        # Find records missing designer or description
        lots = db.query(HistoricalHammer).filter(
            HistoricalHammer.designer_name.is_(None),
            HistoricalHammer.was_sold == 1,
        ).limit(limit).all()

        logger.info(f"Found {len(lots)} lots missing detail data")

        for i, lot in enumerate(lots, 1):
            logger.info(f"[{i}/{len(lots)}] Enriching {lot.external_lot_id}: {lot.title[:60]}")

            try:
                detail = await fetch_ended_lot_detail(lot.lot_url)

                if detail.get("designer_mentions"):
                    lot.designer_name = detail["designer_mentions"][0]
                if detail.get("description") and not lot.description:
                    lot.description = detail["description"]
                if detail.get("material_mentions") and not lot.materials:
                    lot.materials = detail["material_mentions"]
                if detail.get("hammer_price") and not lot.hammer_price:
                    lot.hammer_price = detail["hammer_price"]

                db.commit()

            except Exception as e:
                logger.error(f"  Error enriching {lot.external_lot_id}: {e}")
                continue

        logger.info("Enrichment complete")

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Fetch historical hammer prices from Auctionet ended auctions"
    )
    subparsers = parser.add_subparsers(dest="command")

    # Broad sweep
    broad_parser = subparsers.add_parser("broad", help="Broad sweep of ended auctions")
    broad_parser.add_argument("--pages", type=int, default=10, help="Max pages (default: 10)")

    # Designer search
    des_parser = subparsers.add_parser("designer", help="Search for a specific designer")
    des_parser.add_argument("name", help="Designer name (e.g., 'Hans Wegner')")
    des_parser.add_argument("--pages", type=int, default=5, help="Max pages (default: 5)")

    # Priority designers
    pri_parser = subparsers.add_parser("priority", help="Scrape all priority designers from config")
    pri_parser.add_argument("--pages", type=int, default=5, help="Max pages per designer (default: 5)")

    # Enrich details
    enr_parser = subparsers.add_parser("enrich", help="Fetch detail pages for lots missing data")
    enr_parser.add_argument("--limit", type=int, default=50, help="Max lots to enrich (default: 50)")

    args = parser.parse_args()

    if args.command == "broad":
        asyncio.run(broad_sweep(args.pages))
    elif args.command == "designer":
        asyncio.run(designer_search(args.name, args.pages))
    elif args.command == "priority":
        asyncio.run(priority_designers(args.pages))
    elif args.command == "enrich":
        asyncio.run(enrich_details(args.limit))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
