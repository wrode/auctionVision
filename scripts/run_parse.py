#!/usr/bin/env python3
"""Parse fetched HTML snapshots and extract structured lot data."""
import argparse
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


def load_snapshot(snapshot_path: Path) -> str:
    """Load HTML snapshot from file."""
    try:
        with open(snapshot_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Snapshot not found: {snapshot_path}")
        raise
    except Exception as e:
        logger.error(f"Failed to load snapshot {snapshot_path}: {e}")
        raise


def estimate_in_sek(estimate: float | None, currency: str | None, eur_to_sek: float) -> float:
    """Convert an estimate to SEK for filtering."""
    if estimate is None:
        return 0.0
    if currency and currency.upper() == "EUR":
        return estimate * eur_to_sek
    if currency and currency.upper() == "SEK":
        return estimate
    # Default: assume EUR (Auctionet standard)
    return estimate * eur_to_sek


def build_designer_keywords():
    """Build a set of lowercase name fragments from designers.yaml for cheap matching."""
    from backend.config import load_yaml_config
    config = load_yaml_config("designers.yaml")
    keywords = set()
    for d in config.get("seed_designers", []):
        # Add last name (most distinctive part)
        name = d["name"]
        keywords.add(name.lower())
        for alias in d.get("aliases", []):
            keywords.add(alias.lower())
        for producer in d.get("producers", []):
            keywords.add(producer.lower())
    for d in config.get("adjacent_designers", []):
        keywords.add(d["name"].lower())
    return keywords


def title_has_known_designer(title: str, designer_raw: list[str] | None, keywords: set[str]) -> str | None:
    """Check if title or designer mentions contain a known designer/producer.
    Returns the matched keyword or None."""
    text = title.lower()
    # Also check raw designer mentions from parser
    if designer_raw:
        text += " " + " ".join(d.lower() for d in designer_raw)
    for kw in keywords:
        if kw in text:
            return kw
    return None


def normalize_image_urls(image_urls: list[str] | None) -> list[str]:
    """Deduplicate image URLs while preserving order."""
    seen: set[str] = set()
    normalized: list[str] = []
    for url in image_urls or []:
        if not url or url in seen:
            continue
        seen.add(url)
        normalized.append(url)
    return normalized


def sync_lot_images(db, lot_id: int, image_urls: list[str] | None):
    """Upsert parsed image URLs into lot_images."""
    from backend.models import LotImage

    normalized = normalize_image_urls(image_urls)
    existing = db.query(LotImage).filter(LotImage.lot_id == lot_id).all()
    existing_by_url = {img.image_url: img for img in existing}
    keep_urls = set(normalized)

    for sort_order, url in enumerate(normalized):
        image = existing_by_url.get(url)
        if image:
            image.sort_order = sort_order
        else:
            db.add(LotImage(
                lot_id=lot_id,
                image_url=url,
                sort_order=sort_order,
            ))

    for image in existing:
        if image.image_url not in keep_urls and not image.local_path:
            db.delete(image)


def update_lot_status_from_parsed(db, lot, parsed_fields):
    """Update lot status based on parsed auction state (sold/unsold)."""
    if parsed_fields.hammer_price is not None:
        lot.status = "sold"
        logger.info(f"  → Lot {lot.external_lot_id} SOLD for {parsed_fields.hammer_price} {parsed_fields.currency}")
    elif parsed_fields.sold_at is not None and parsed_fields.hammer_price is None:
        # Has an end time from a finished auction but no winning bid → unsold
        lot.status = "unsold"
        logger.info(f"  → Lot {lot.external_lot_id} UNSOLD")


def upsert_parsed_record(db, lot_id: int, lot_fetch_id: int, parser_version: str, parsed_fields):
    """Create or update parsed metadata for a fetched lot snapshot."""
    from backend.models import ParsedLotFields

    parsed_record = db.query(ParsedLotFields).filter(
        ParsedLotFields.lot_id == lot_id,
        ParsedLotFields.lot_fetch_id == lot_fetch_id,
    ).order_by(ParsedLotFields.created_at.desc()).first()

    if not parsed_record:
        parsed_record = ParsedLotFields(
            lot_id=lot_id,
            lot_fetch_id=lot_fetch_id,
            parser_version=parser_version,
            created_at=datetime.utcnow(),
        )

    fallback_bid = None
    if parsed_fields.current_bid is None:
        fallback_bid = db.query(ParsedLotFields.current_bid).filter(
            ParsedLotFields.lot_id == lot_id,
            ParsedLotFields.current_bid.isnot(None),
            ParsedLotFields.current_bid > 0,
        ).order_by(ParsedLotFields.created_at.desc()).first()

    parsed_record.parser_version = parser_version
    parsed_record.title = parsed_fields.title
    parsed_record.subtitle = parsed_fields.subtitle
    parsed_record.description = parsed_fields.description
    parsed_record.category_raw = parsed_fields.category_raw
    parsed_record.condition_text = parsed_fields.condition_text
    parsed_record.dimensions_text = parsed_fields.dimensions_text
    parsed_record.current_bid = (
        parsed_fields.current_bid
        if parsed_fields.current_bid is not None
        else (fallback_bid[0] if fallback_bid else None)
    )
    parsed_record.bid_count = parsed_fields.bid_count
    parsed_record.hammer_price = parsed_fields.hammer_price
    parsed_record.sold_at = parsed_fields.sold_at
    parsed_record.estimate_low = parsed_fields.estimate_low
    parsed_record.estimate_high = parsed_fields.estimate_high
    parsed_record.currency = parsed_fields.currency
    parsed_record.auction_end_time = parsed_fields.auction_end_time
    parsed_record.time_left_text = parsed_fields.time_left_text
    parsed_record.provenance_text = parsed_fields.provenance_text
    parsed_record.seller_location = parsed_fields.seller_location
    parsed_record.auction_house_name = parsed_fields.auction_house_name
    parsed_record.raw_designer_mentions = parsed_fields.raw_designer_mentions
    parsed_record.raw_material_mentions = parsed_fields.raw_material_mentions
    parsed_record.parse_confidence = parsed_fields.parse_confidence
    parsed_record.created_at = datetime.utcnow()

    db.add(parsed_record)
    sync_lot_images(db, lot_id, parsed_fields.image_urls)

    # Update lot status if auction has ended
    from backend.models import Lot
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if lot:
        update_lot_status_from_parsed(db, lot, parsed_fields)

    return parsed_record


def parse_lots_unparsed(source_name: str = "auctionet"):
    """Find and parse all unparsed lot fetches."""
    import time
    from backend.database import SessionLocal, init_db
    from backend.models import Source, LotFetch
    from backend.config import load_yaml_config, settings
    from backend.parsers.auctionet import AuctionetParser

    init_db()
    db = SessionLocal()

    # Load filter config
    scoring_config = load_yaml_config("scoring.yaml")
    filters = scoring_config.get("filters", {})
    min_estimate_sek = filters.get("min_estimate_sek", 2000)
    eur_to_sek = filters.get("eur_to_sek_rate", 11.49)

    # Visual triage config
    triage_config = scoring_config.get("visual_triage", {})
    triage_enabled = settings.enable_visual_triage and bool(settings.claude_api_key)
    triage_model = triage_config.get("model", "claude-haiku-4-5-20251001")
    triage_max_tokens = triage_config.get("max_tokens", 100)
    triage_max_calls = triage_config.get("max_calls_per_run", 50)
    triage_throttle = triage_config.get("throttle_seconds", 0.5)
    triage_call_count = 0
    triage_rescue_count = 0

    if triage_enabled:
        from backend.ingestion.image_triage import run_image_triage
        logger.info(f"Visual triage enabled (model={triage_model}, max_calls={triage_max_calls})")
    else:
        reason = "no API key" if not settings.claude_api_key else "disabled in .env"
        logger.info(f"Visual triage disabled ({reason})")

    # Build designer keywords for bypass
    designer_keywords = build_designer_keywords()

    try:
        # Get source
        source = db.query(Source).filter(Source.name == source_name).first()
        if not source:
            logger.error(f"Source not found: {source_name}")
            return

        # Find lot fetches without parsed fields
        unparsed_fetches = db.query(LotFetch).filter(
            LotFetch.lot.has(source_id=source.id),
            ~LotFetch.parsed_fields.any(),
            LotFetch.success == 1,
        ).all()

        logger.info(f"Found {len(unparsed_fetches)} unparsed lot fetches")
        logger.info(f"Filter: min estimate {min_estimate_sek} SEK (~{min_estimate_sek / eur_to_sek:.0f} EUR)")

        parser = AuctionetParser()
        parsed_count = 0
        filtered_count = 0

        for lot_fetch in unparsed_fetches:
            lot = lot_fetch.lot
            lot_url = lot.lot_url

            # Load raw HTML
            if not lot_fetch.raw_html_path:
                logger.warning(f"No raw_html_path for LotFetch {lot_fetch.id}")
                continue

            try:
                raw_html = load_snapshot(Path(lot_fetch.raw_html_path))
            except Exception as e:
                logger.error(f"Failed to load HTML for lot {lot.external_lot_id}: {e}")
                continue

            # Parse
            try:
                parsed_fields = parser.parse(raw_html, lot_url)

                # --- Minimum estimate filter (with designer + visual triage bypass) ---
                est = parsed_fields.estimate_low or parsed_fields.estimate_high
                est_sek = estimate_in_sek(est, parsed_fields.currency, eur_to_sek)
                designer_match = title_has_known_designer(
                    parsed_fields.title or "",
                    parsed_fields.raw_designer_mentions,
                    designer_keywords,
                )
                if est_sek < min_estimate_sek and not designer_match:
                    # Check cached triage result first
                    if lot.visual_triage_result == "YES":
                        logger.info(
                            f"RESCUE {lot.external_lot_id}: cached visual triage YES — {lot.visual_triage_reason}"
                        )
                        triage_rescue_count += 1
                    elif triage_enabled and triage_call_count < triage_max_calls and lot.visual_triage_result is None:
                        # Run visual triage on this lot
                        result, reason = run_image_triage(
                            parsed_fields.image_urls or [],
                            api_key=settings.claude_api_key,
                            model=triage_model,
                            max_tokens=triage_max_tokens,
                        )
                        lot.visual_triage_result = result
                        lot.visual_triage_reason = reason[:500]
                        db.commit()
                        triage_call_count += 1
                        time.sleep(triage_throttle)

                        if result == "YES":
                            logger.info(f"RESCUE {lot.external_lot_id}: visual triage YES — {reason}")
                            triage_rescue_count += 1
                        else:
                            lot.status = "filtered"
                            db.commit()
                            filtered_count += 1
                            logger.info(
                                f"SKIP {lot.external_lot_id}: estimate {est} {parsed_fields.currency} "
                                f"(~{est_sek:.0f} SEK) + visual triage NO — {reason}"
                            )
                            continue
                    else:
                        # No triage available — filter as before
                        lot.status = "filtered"
                        db.commit()
                        filtered_count += 1
                        logger.info(
                            f"SKIP {lot.external_lot_id}: estimate {est} {parsed_fields.currency} "
                            f"(~{est_sek:.0f} SEK) < {min_estimate_sek} SEK"
                        )
                        continue
                if designer_match and est_sek < min_estimate_sek:
                    logger.info(
                        f"KEEP {lot.external_lot_id}: est {est} {parsed_fields.currency} "
                        f"(~{est_sek:.0f} SEK) below threshold but matched designer: {designer_match}"
                    )

                upsert_parsed_record(
                    db,
                    lot_id=lot.id,
                    lot_fetch_id=lot_fetch.id,
                    parser_version=parser.parser_version,
                    parsed_fields=parsed_fields,
                )
                db.commit()

                parsed_count += 1
                logger.info(
                    f"Parsed {lot.external_lot_id}: {parsed_fields.title} "
                    f"| est {est} {parsed_fields.currency} (~{est_sek:.0f} SEK)"
                )

            except Exception as e:
                logger.error(f"Error parsing lot {lot.external_lot_id}: {e}")
                continue

        triage_msg = f", {triage_rescue_count} rescued by visual triage ({triage_call_count} API calls)" if triage_call_count else ""
        logger.info(f"Parsing complete: {parsed_count} kept, {filtered_count} filtered{triage_msg}")

    finally:
        db.close()


def parse_single_lot(lot_id: str):
    """Parse a single lot by ID or fetch a specific snapshot."""
    from backend.database import SessionLocal, init_db
    from backend.models import Lot, LotFetch
    from backend.parsers.auctionet import AuctionetParser

    init_db()
    db = SessionLocal()

    try:
        lot = db.query(Lot).filter(Lot.external_lot_id == lot_id).first()
        if not lot:
            logger.error(f"Lot not found: {lot_id}")
            return

        logger.info(f"Parsing lot {lot_id}: {lot.lot_url}")

        # Get the most recent fetch for this lot
        lot_fetch = db.query(LotFetch).filter(
            LotFetch.lot_id == lot.id,
            LotFetch.success == 1,
        ).order_by(LotFetch.fetched_at.desc()).first()

        if not lot_fetch:
            logger.error(f"No successful fetch found for lot {lot_id}")
            return

        # Load and parse HTML
        if not lot_fetch.raw_html_path:
            logger.error(f"No raw_html_path for lot {lot_id}")
            return

        try:
            raw_html = load_snapshot(Path(lot_fetch.raw_html_path))
        except Exception as e:
            logger.error(f"Failed to load HTML: {e}")
            return

        # Parse
        parser = AuctionetParser()
        parsed_fields = parser.parse(raw_html, lot.lot_url)

        upsert_parsed_record(
            db,
            lot_id=lot.id,
            lot_fetch_id=lot_fetch.id,
            parser_version=parser.parser_version,
            parsed_fields=parsed_fields,
        )
        db.commit()

        logger.info(f"Successfully parsed lot {lot_id}")
        logger.info(f"  Title: {parsed_fields.title}")
        logger.info(f"  Category: {parsed_fields.category_raw}")
        logger.info(f"  Current bid: {parsed_fields.current_bid} {parsed_fields.currency}")
        logger.info(f"  Images: {len(normalize_image_urls(parsed_fields.image_urls))}")

    finally:
        db.close()


def backfill_latest_metadata(source_name: str = "auctionet", status: str = "active", limit: int | None = None):
    """Reparse the latest successful fetch for existing lots and sync bids/images."""
    from backend.database import SessionLocal, init_db
    from backend.models import Source, Lot, LotFetch
    from backend.parsers.auctionet import AuctionetParser

    init_db()
    db = SessionLocal()

    try:
        source = db.query(Source).filter(Source.name == source_name).first()
        if not source:
            logger.error(f"Source not found: {source_name}")
            return

        query = db.query(Lot).filter(Lot.source_id == source.id)
        if status != "all":
            query = query.filter(Lot.status == status)
        lots = query.order_by(Lot.id.asc()).limit(limit).all() if limit else query.order_by(Lot.id.asc()).all()

        parser = AuctionetParser()
        updated = 0
        with_bid = 0
        with_images = 0

        for lot in lots:
            lot_fetch = db.query(LotFetch).filter(
                LotFetch.lot_id == lot.id,
                LotFetch.success == 1,
                LotFetch.raw_html_path.isnot(None),
            ).order_by(LotFetch.fetched_at.desc()).first()

            if not lot_fetch or not lot_fetch.raw_html_path:
                continue

            try:
                raw_html = load_snapshot(Path(lot_fetch.raw_html_path))
                parsed_fields = parser.parse(raw_html, lot.lot_url)
                upsert_parsed_record(
                    db,
                    lot_id=lot.id,
                    lot_fetch_id=lot_fetch.id,
                    parser_version=parser.parser_version,
                    parsed_fields=parsed_fields,
                )
                db.commit()
                updated += 1
                if parsed_fields.current_bid is not None and parsed_fields.current_bid > 0:
                    with_bid += 1
                if normalize_image_urls(parsed_fields.image_urls):
                    with_images += 1
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to backfill lot {lot.external_lot_id}: {e}")

        logger.info(
            f"Backfill complete: {updated} lots refreshed, {with_bid} with current bids, {with_images} with images"
        )

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Parse fetched HTML snapshots and extract lot data"
    )
    subparsers = parser.add_subparsers(dest="command")

    lot_parser = subparsers.add_parser(
        "lot",
        help="Parse a single lot by ID"
    )
    lot_parser.add_argument("lot_id", help="Lot ID to parse")

    all_parser = subparsers.add_parser(
        "all",
        help="Parse all unparsed lots from a source"
    )
    all_parser.add_argument(
        "--source",
        default="auctionet",
        help="Source name (default: auctionet)"
    )

    backfill_parser = subparsers.add_parser(
        "backfill",
        help="Reparse latest fetched HTML for existing lots and sync bids/images"
    )
    backfill_parser.add_argument(
        "--source",
        default="auctionet",
        help="Source name (default: auctionet)"
    )
    backfill_parser.add_argument(
        "--status",
        default="active",
        help="Lot status to backfill (default: active, use 'all' for every lot)"
    )
    backfill_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max lots to process"
    )

    args = parser.parse_args()

    if args.command == "lot":
        parse_single_lot(args.lot_id)
    elif args.command == "all":
        parse_lots_unparsed(args.source)
    elif args.command == "backfill":
        backfill_latest_metadata(args.source, args.status, args.limit)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
