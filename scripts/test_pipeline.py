#!/usr/bin/env python3
"""Test the complete fetch and parse pipeline with mock data."""
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


def create_test_data():
    """Create test Source, Lot, and LotFetch records from existing snapshots."""
    from backend.database import SessionLocal, init_db
    from backend.models import Source, Lot, LotFetch
    import hashlib

    init_db()
    db = SessionLocal()

    try:
        # Create or get source
        source = db.query(Source).filter(Source.name == "auctionet").first()
        if not source:
            source = Source(
                name="auctionet",
                base_url="https://auctionet.com",
                parser_name="auctionet_v1",
            )
            db.add(source)
            db.commit()
            logger.info("Created Source: auctionet")

        # Create test lots from existing snapshot files
        snapshots_dir = Path(__file__).parent.parent / "data" / "snapshots" / "auctionet" / "2026-03-27"
        if not snapshots_dir.exists():
            logger.error(f"Snapshots directory not found: {snapshots_dir}")
            return

        snapshot_files = list(snapshots_dir.glob("*.html"))
        logger.info(f"Found {len(snapshot_files)} snapshot files")

        for snapshot_file in snapshot_files:
            # Parse lot ID from filename
            filename = snapshot_file.name
            lot_id = filename.split("_")[0]

            # Check if lot already exists
            existing_lot = db.query(Lot).filter(
                Lot.source_id == source.id,
                Lot.external_lot_id == lot_id,
            ).first()

            if existing_lot:
                logger.info(f"Lot {lot_id} already exists, skipping")
                continue

            # Create lot
            lot_url = f"https://auctionet.com/en/lot/{lot_id}"
            lot = Lot(
                source_id=source.id,
                external_lot_id=lot_id,
                lot_url=lot_url,
            )
            db.add(lot)
            db.commit()
            logger.info(f"Created Lot: {lot_id}")

            # Read snapshot and create LotFetch
            with open(snapshot_file, 'r') as f:
                content = f.read()

            content_hash = hashlib.sha256(content.encode()).hexdigest()

            lot_fetch = LotFetch(
                lot_id=lot.id,
                fetched_at=datetime.utcnow(),
                fetch_type="full",
                http_status=200,
                content_hash=content_hash,
                raw_html_path=str(snapshot_file),
                success=1,
                error_message=None,
            )
            db.add(lot_fetch)
            db.commit()
            logger.info(f"Created LotFetch for {lot_id}: {snapshot_file}")

            lot.last_fetched_at = datetime.utcnow()
            db.commit()

        logger.info("Test data creation complete")

    finally:
        db.close()


def test_parse():
    """Test parsing the test data."""
    from backend.database import SessionLocal, init_db
    from backend.models import Source, Lot, LotFetch, ParsedLotFields
    from backend.parsers.auctionet import AuctionetParser

    init_db()
    db = SessionLocal()

    try:
        source = db.query(Source).filter(Source.name == "auctionet").first()
        if not source:
            logger.error("Source not found, run create_test_data first")
            return

        # Find unparsed fetches
        unparsed_fetches = db.query(LotFetch).filter(
            LotFetch.lot.has(source_id=source.id),
            LotFetch.success == 1,
        ).all()

        logger.info(f"Found {len(unparsed_fetches)} lot fetches to parse")

        parser = AuctionetParser()
        parsed_count = 0

        for lot_fetch in unparsed_fetches:
            lot = lot_fetch.lot
            lot_url = lot.lot_url

            logger.info(f"Parsing lot {lot.external_lot_id}: {lot_url}")

            # Load and parse HTML
            try:
                with open(lot_fetch.raw_html_path, 'r') as f:
                    raw_html = f.read()
            except Exception as e:
                logger.error(f"Failed to load HTML: {e}")
                continue

            # Parse
            try:
                parsed_fields = parser.parse(raw_html, lot_url)

                # Save
                parsed_record = ParsedLotFields(
                    lot_id=lot.id,
                    lot_fetch_id=lot_fetch.id,
                    parser_version=parser.parser_version,
                    title=parsed_fields.title,
                    subtitle=parsed_fields.subtitle,
                    description=parsed_fields.description,
                    category_raw=parsed_fields.category_raw,
                    condition_text=parsed_fields.condition_text,
                    dimensions_text=parsed_fields.dimensions_text,
                    current_bid=parsed_fields.current_bid,
                    estimate_low=parsed_fields.estimate_low,
                    estimate_high=parsed_fields.estimate_high,
                    currency=parsed_fields.currency,
                    auction_end_time=parsed_fields.auction_end_time,
                    time_left_text=parsed_fields.time_left_text,
                    provenance_text=parsed_fields.provenance_text,
                    seller_location=parsed_fields.seller_location,
                    auction_house_name=parsed_fields.auction_house_name,
                    raw_designer_mentions=parsed_fields.raw_designer_mentions,
                    raw_material_mentions=parsed_fields.raw_material_mentions,
                    parse_confidence=parsed_fields.parse_confidence,
                    created_at=datetime.utcnow(),
                )
                db.add(parsed_record)
                db.commit()

                parsed_count += 1
                logger.info(f"✓ Parsed lot {lot.external_lot_id}")
                logger.info(f"  Title: {parsed_fields.title}")
                logger.info(f"  Category: {parsed_fields.category_raw}")
                logger.info(f"  Current bid: {parsed_fields.current_bid} {parsed_fields.currency}")
                logger.info(f"  Confidence: {parsed_fields.parse_confidence}")

            except Exception as e:
                logger.error(f"Error parsing lot {lot.external_lot_id}: {e}")
                import traceback
                traceback.print_exc()

        logger.info(f"\nParsing complete: {parsed_count} lots successfully parsed")

        # Print summary
        logger.info("\n=== SUMMARY ===")
        all_lots = db.query(Lot).filter(Lot.source_id == source.id).all()
        logger.info(f"Total lots: {len(all_lots)}")

        for lot in all_lots:
            parsed = db.query(ParsedLotFields).filter(ParsedLotFields.lot_id == lot.id).first()
            if parsed:
                logger.info(f"  Lot {lot.external_lot_id}: {parsed.title} ({parsed.currency} {parsed.current_bid})")
            else:
                logger.info(f"  Lot {lot.external_lot_id}: NOT PARSED")

    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test the crawl and parse pipeline")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("create", help="Create test data from snapshot files")
    subparsers.add_parser("parse", help="Parse test data")

    args = parser.parse_args()

    if args.command == "create":
        create_test_data()
    elif args.command == "parse":
        test_parse()
    else:
        logger.info("Usage: test_pipeline.py {create|parse}")
