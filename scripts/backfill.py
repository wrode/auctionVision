#!/usr/bin/env python3
"""Backfill: re-parse or re-enrich existing lots."""
import argparse
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


class BackfillStats:
    """Track backfill statistics."""

    def __init__(self):
        self.total = 0
        self.succeeded = 0
        self.failed = 0
        self.errors = []

    def record_success(self, lot_id: str):
        self.total += 1
        self.succeeded += 1

    def record_failure(self, lot_id: str, error: str):
        self.total += 1
        self.failed += 1
        self.errors.append((lot_id, error))

    def report(self):
        logger.info("=" * 60)
        logger.info("BACKFILL SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total processed: {self.total}")
        logger.info(f"Succeeded: {self.succeeded}")
        logger.info(f"Failed: {self.failed}")
        if self.failed > 0:
            logger.info("\nFailures:")
            for lot_id, error in self.errors[:10]:  # Show first 10
                logger.info(f"  {lot_id}: {error}")
            if self.failed > 10:
                logger.info(f"  ... and {self.failed - 10} more")


async def backfill_parse(filter_lot_ids=None):
    """Re-parse all or specified lots."""
    logger.info("Starting parsing backfill...")
    stats = BackfillStats()

    snapshots_dir = Path("data/snapshots")
    if not snapshots_dir.exists():
        logger.warning(f"Snapshots directory not found: {snapshots_dir}")
        return

    html_files = list(snapshots_dir.glob("*.html"))
    logger.info(f"Found {len(html_files)} snapshot files to reparse")

    # Import parsing function
    try:
        from scripts.run_parse import parse_lot
        parse_func = parse_lot
    except ImportError:
        logger.error("Could not import parse_lot function")
        return

    for snapshot_file in html_files:
        lot_id = snapshot_file.stem

        if filter_lot_ids and lot_id not in filter_lot_ids:
            continue

        try:
            await parse_func(lot_id, str(snapshot_file))
            stats.record_success(lot_id)
        except Exception as e:
            logger.error(f"Failed to parse {lot_id}: {e}")
            stats.record_failure(lot_id, str(e))

    stats.report()


async def backfill_enrich(filter_lot_ids=None):
    """Re-enrich all or specified lots."""
    logger.info("Starting enrichment backfill...")
    stats = BackfillStats()

    # In a real implementation, this would query the database for all lot IDs
    lot_ids = filter_lot_ids or []

    if not lot_ids:
        logger.warning("No lot IDs specified. Use --lot-ids or query database.")
        logger.info("To enrich specific lots, pass: --lot-ids lot1,lot2,lot3")
        return

    try:
        from scripts.run_enrich import enrich_lot
        enrich_func = enrich_lot
    except ImportError:
        logger.error("Could not import enrich_lot function")
        return

    for lot_id in lot_ids:
        try:
            await enrich_func(lot_id)
            stats.record_success(lot_id)
        except Exception as e:
            logger.error(f"Failed to enrich {lot_id}: {e}")
            stats.record_failure(lot_id, str(e))

    stats.report()


def main():
    parser = argparse.ArgumentParser(
        description="Backfill: re-parse or re-enrich lots in bulk"
    )
    subparsers = parser.add_subparsers(dest="command")

    parse_parser = subparsers.add_parser(
        "parse",
        help="Re-parse all or specified lots from snapshots"
    )
    parse_parser.add_argument(
        "--lot-ids",
        help="Comma-separated lot IDs to reparse (default: all in data/snapshots)"
    )

    enrich_parser = subparsers.add_parser(
        "enrich",
        help="Re-enrich all or specified lots"
    )
    enrich_parser.add_argument(
        "--lot-ids",
        required=True,
        help="Comma-separated lot IDs to re-enrich"
    )

    args = parser.parse_args()

    import asyncio

    lot_ids = None
    if args.lot_ids:
        lot_ids = [lid.strip() for lid in args.lot_ids.split(",")]

    if args.command == "parse":
        asyncio.run(backfill_parse(filter_lot_ids=lot_ids))
    elif args.command == "enrich":
        asyncio.run(backfill_enrich(filter_lot_ids=lot_ids))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
