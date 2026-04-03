#!/usr/bin/env python3
"""Visual triage: identify lots that need image-based assessment.

This script has two modes:
  export  — Download images and print lot data for subagent triage
  import  — Import YES/NO results back into the database

Usage:
  # 1. Export lots needing triage (downloads images, prints JSON for agents)
  python scripts/visual_triage.py export

  # 2. After agents have assessed, import results:
  python scripts/visual_triage.py import 4845151=YES 4888742=NO ...
  # Or from a file:
  python scripts/visual_triage.py import --file data/triage_results.txt
"""
import argparse
import json
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TRIAGE_IMAGES_DIR = Path("data/triage_images")


def export_triage_lots():
    """Find filtered lots needing triage, download images, output lot list."""
    import httpx
    from backend.database import SessionLocal, init_db
    from backend.models import Lot, LotFetch
    from backend.parsers.auctionet import AuctionetParser

    init_db()
    db = SessionLocal()
    TRIAGE_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    # Find filtered lots without a triage result
    filtered = db.query(Lot).filter(
        Lot.status == "filtered",
        Lot.visual_triage_result.is_(None),
    ).all()

    if not filtered:
        logger.info("No lots need visual triage — all have been assessed or passed filters.")
        db.close()
        return []

    parser = AuctionetParser()
    client = httpx.Client(timeout=10.0)
    lots_for_triage = []

    for lot in filtered:
        fetch = db.query(LotFetch).filter(
            LotFetch.lot_id == lot.id,
            LotFetch.success == 1,
        ).order_by(LotFetch.fetched_at.desc()).first()

        if not fetch or not fetch.raw_html_path:
            continue

        try:
            html = Path(fetch.raw_html_path).read_text()
            parsed = parser.parse(html, lot.lot_url or "")
        except Exception:
            continue

        if not parsed.image_urls:
            continue

        # Get best image URL
        img_url = parsed.image_urls[0]
        if "medium_" in img_url:
            img_url = img_url.replace("medium_", "large_")
        elif "thumb_" in img_url:
            img_url = img_url.replace("thumb_", "large_")

        # Download image
        img_path = TRIAGE_IMAGES_DIR / f"{lot.external_lot_id}.jpg"
        if not img_path.exists():
            try:
                resp = client.get(img_url, follow_redirects=True)
                resp.raise_for_status()
                img_path.write_bytes(resp.content)
            except Exception as e:
                logger.warning(f"Failed to download image for {lot.external_lot_id}: {e}")
                continue

        lots_for_triage.append({
            "ext_id": lot.external_lot_id,
            "title": parsed.title or "Unknown",
            "estimate": parsed.estimate_low,
            "currency": parsed.currency or "EUR",
            "image_path": str(img_path.resolve()),
        })

    client.close()
    db.close()

    logger.info(f"Exported {len(lots_for_triage)} lots for visual triage")
    logger.info(f"Images saved to: {TRIAGE_IMAGES_DIR.resolve()}")

    # Print as JSON for easy consumption
    print(json.dumps(lots_for_triage, indent=2))
    return lots_for_triage


def import_triage_results(results: dict[str, tuple[str, str]]):
    """Import triage results into the database.

    Args:
        results: {external_lot_id: (YES|NO, reason)}
    """
    from backend.database import SessionLocal, init_db
    from backend.models import Lot

    init_db()
    db = SessionLocal()

    rescued = 0
    confirmed_filtered = 0

    for ext_id, (result, reason) in results.items():
        lot = db.query(Lot).filter(Lot.external_lot_id == ext_id).first()
        if not lot:
            logger.warning(f"Lot {ext_id} not found in database")
            continue

        lot.visual_triage_result = result.upper()
        lot.visual_triage_reason = reason[:500]

        if result.upper() == "YES":
            lot.status = "active"
            rescued += 1
            logger.info(f"RESCUE {ext_id}: {reason[:80]}")
        else:
            confirmed_filtered += 1

    db.commit()
    db.close()
    logger.info(f"Imported: {rescued} rescued, {confirmed_filtered} confirmed filtered")


def parse_result_args(args: list[str]) -> dict[str, tuple[str, str]]:
    """Parse 'LOT_ID=YES reason' or 'LOT_ID=NO reason' arguments."""
    results = {}
    for arg in args:
        if "=" not in arg:
            continue
        ext_id, rest = arg.split("=", 1)
        parts = rest.split(" ", 1)
        verdict = parts[0].upper()
        reason = parts[1] if len(parts) > 1 else ""
        if verdict in ("YES", "NO"):
            results[ext_id.strip()] = (verdict, reason.strip())
    return results


def parse_result_file(filepath: str) -> dict[str, tuple[str, str]]:
    """Parse results from a file. Each line: LOT_ID=YES|NO reason"""
    results = {}
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                parsed = parse_result_args([line])
                results.update(parsed)
    return results


def main():
    parser = argparse.ArgumentParser(description="Visual triage for auction lots")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("export", help="Export lots needing triage (downloads images, prints JSON)")

    import_parser = subparsers.add_parser("import", help="Import YES/NO triage results")
    import_parser.add_argument("results", nargs="*", help="LOT_ID=YES|NO [reason]")
    import_parser.add_argument("--file", "-f", help="Read results from file")

    args = parser.parse_args()

    if args.command == "export":
        export_triage_lots()
    elif args.command == "import":
        results = {}
        if args.file:
            results = parse_result_file(args.file)
        if args.results:
            results.update(parse_result_args(args.results))
        if not results:
            print("No results to import. Provide LOT_ID=YES|NO args or --file.")
            sys.exit(1)
        import_triage_results(results)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
