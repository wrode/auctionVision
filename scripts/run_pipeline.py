#!/usr/bin/env python3
"""Full pipeline: fetch → parse → triage → ready for enrichment.

Usage:
  python scripts/run_pipeline.py 100          # refetch active + fetch new + parse + triage
  python scripts/run_pipeline.py --refetch    # only re-scrape active lots for bid/status updates
  python scripts/run_pipeline.py --parse-only # skip fetch, just parse + triage
  python scripts/run_pipeline.py --status     # show pipeline state
"""
import asyncio
import sys
import logging
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def step_refetch():
    """Re-scrape all active lots to get updated bids and detect sold/unsold."""
    from backend.config import settings
    from backend.database import SessionLocal, init_db
    from backend.ingestion.fetcher import AuctionetFetcher
    from backend.models import Lot, LotFetch
    from backend.parsers.auctionet import AuctionetParser
    from scripts.run_parse import upsert_parsed_record, load_snapshot

    settings.ensure_dirs()
    init_db()
    db = SessionLocal()
    fetcher = AuctionetFetcher()
    parser = AuctionetParser()

    try:
        active_lots = db.query(Lot).filter(Lot.status == "active").all()
        logger.info(f"Re-fetching {len(active_lots)} active lots for bid updates...")

        ok = 0
        sold = 0
        unsold = 0
        fail = 0

        for i, lot in enumerate(active_lots):
            result = await fetcher.fetch_lot_detail(lot.lot_url)
            if not result.get("success"):
                logger.warning(f"  [{i+1}/{len(active_lots)}] FAIL {lot.external_lot_id}: {result.get('error_message')}")
                fail += 1
                continue

            # Create new fetch record
            lot_fetch = LotFetch(
                lot_id=lot.id,
                fetched_at=datetime.now(timezone.utc),
                fetch_type="refetch",
                http_status=result["http_status"],
                content_hash=result["content_hash"],
                raw_html_path=result["raw_html_path"],
                success=True,
            )
            db.add(lot_fetch)
            lot.last_fetched_at = datetime.now(timezone.utc)
            db.commit()

            # Parse immediately to update bid/status
            try:
                raw_html = load_snapshot(Path(result["raw_html_path"]))
                parsed_fields = parser.parse(raw_html, lot.lot_url)
                upsert_parsed_record(
                    db,
                    lot_id=lot.id,
                    lot_fetch_id=lot_fetch.id,
                    parser_version=parser.parser_version,
                    parsed_fields=parsed_fields,
                )
                db.commit()

                if lot.status == "sold":
                    sold += 1
                elif lot.status == "unsold":
                    unsold += 1

                ok += 1
                bid_info = f"bid={parsed_fields.current_bid}" if parsed_fields.current_bid else "no bids"
                count_info = f"({parsed_fields.bid_count} bids)" if parsed_fields.bid_count else ""
                logger.info(f"  [{i+1}/{len(active_lots)}] {lot.external_lot_id}: {bid_info} {count_info} [{lot.status}]")
            except Exception as e:
                logger.error(f"  Parse error for {lot.external_lot_id}: {e}")
                ok += 1  # fetch succeeded even if parse failed

            if (i + 1) % 10 == 0:
                logger.info(f"  Progress: {i+1}/{len(active_lots)} ({ok} ok, {fail} fail)")

        logger.info(f"Refetch done: {ok} updated, {sold} sold, {unsold} unsold, {fail} failed")
        return ok

    finally:
        await fetcher.close()
        db.close()


async def step_fetch(max_lots: int = 100, min_score: int = 0):
    """Step 1: Fetch listing pages, pre-filter by URL slug score, then fetch detail pages.

    Args:
        max_lots: Max detail pages to fetch (after pre-filtering).
        min_score: Minimum pre-filter score to fetch detail page.
                   0 = skip only anti-signal lots (conservative).
                   3 = designer-only mode (aggressive, highest ROI).
    """
    from backend.config import settings
    from backend.database import SessionLocal, init_db
    from backend.ingestion.fetcher import AuctionetFetcher
    from backend.models import Source, Lot, LotFetch
    from backend.prefilter import filter_listing_lots, score_lot_url, classify_lot

    settings.ensure_dirs()
    init_db()
    db = SessionLocal()
    fetcher = AuctionetFetcher()

    try:
        source = db.query(Source).filter(Source.name == "auctionet").first()
        if not source:
            source = Source(
                name="auctionet",
                base_url=settings.auctionet_base_url,
                enabled=True,
                parser_name="auctionet_v2",
            )
            db.add(source)
            db.commit()

        # Build set of already-known lot IDs to skip
        existing_ids = set(
            r[0] for r in db.query(Lot.external_lot_id).filter(
                Lot.source_id == source.id
            ).all()
        )

        # Phase 1: Scrape ALL listing pages (cheap — no detail fetches)
        all_discovered = []
        seen_ids = set()
        page_num = 1
        empty_pages = 0
        logger.info("Phase 1: Scanning listing pages for lot URLs...")
        while True:
            page_lots = await fetcher.fetch_listing_page(page_num, category="furniture")
            if not page_lots:
                empty_pages += 1
                if empty_pages >= 3:
                    break
                page_num += 1
                continue
            empty_pages = 0
            new_on_page = 0
            for ld in page_lots:
                if ld["external_lot_id"] not in seen_ids:
                    seen_ids.add(ld["external_lot_id"])
                    all_discovered.append(ld)
                    new_on_page += 1
            if page_num % 10 == 0:
                logger.info(f"  Page {page_num}: {len(all_discovered)} total discovered")
            page_num += 1
            # Safety limit: don't scrape more than 120 listing pages
            if page_num > 120:
                break

        logger.info(f"Discovered {len(all_discovered)} lots across {page_num - 1} listing pages")

        # Phase 2: Pre-filter score from URL slugs
        auto_lots, gate_lots, skip_lots = filter_listing_lots(
            all_discovered,
            min_score=min_score,
            existing_ids=existing_ids,
        )
        new_total = len(auto_lots) + len(gate_lots)

        logger.info(
            f"Pre-filter results (new lots only):\n"
            f"  🥇 Auto-fetch (score >= 3): {len(auto_lots)}\n"
            f"  🥈 Gate (score 0-2):         {len(gate_lots)}\n"
            f"  🚫 Skipped (score < 0):      {len(skip_lots)}\n"
            f"  ⏭️  Already in DB:            {len(all_discovered) - new_total - len(skip_lots)}"
        )

        # Combine auto + gate lots, prioritize by score (highest first)
        fetch_list = sorted(
            auto_lots + gate_lots,
            key=lambda x: x.get("prefilter_score", 0),
            reverse=True,
        )[:max_lots]

        logger.info(f"Phase 2: Fetching {len(fetch_list)} detail pages (top {max_lots} by score)...")

        # Phase 3: Fetch detail pages for selected lots
        ok = 0
        fail = 0
        for i, lot_data in enumerate(fetch_list):
            ext_id = lot_data["external_lot_id"]
            lot_url = lot_data["lot_url"]
            score = lot_data.get("prefilter_score", 0)
            signals = lot_data.get("prefilter_signals", [])

            lot = db.query(Lot).filter(
                Lot.source_id == source.id,
                Lot.external_lot_id == ext_id,
            ).first()
            if not lot:
                lot = Lot(
                    source_id=source.id,
                    external_lot_id=ext_id,
                    lot_url=lot_url,
                    status="active",
                    first_seen_at=datetime.now(timezone.utc),
                )
                db.add(lot)
                db.commit()
            lot.last_seen_at = datetime.now(timezone.utc)

            result = await fetcher.fetch_lot_detail(lot_url)
            if not result.get("success"):
                logger.warning(f"  [{i+1}/{len(fetch_list)}] FAIL {ext_id}: {result.get('error_message')}")
                fail += 1
                continue

            lot_fetch = LotFetch(
                lot_id=lot.id,
                fetched_at=datetime.now(timezone.utc),
                fetch_type="full",
                http_status=result["http_status"],
                content_hash=result["content_hash"],
                raw_html_path=result["raw_html_path"],
                success=True,
            )
            db.add(lot_fetch)
            lot.last_fetched_at = datetime.now(timezone.utc)
            db.commit()

            ok += 1
            if (i + 1) % 10 == 0:
                logger.info(f"  [{i+1}/{len(fetch_list)}] scraped ({ok} ok, {fail} fail) [score={score}]")

        logger.info(
            f"Fetch done: {ok} scraped, {fail} failed, {len(skip_lots)} pre-filtered out"
        )
        return ok

    finally:
        await fetcher.close()
        db.close()


def step_parse():
    """Step 2: Parse HTML → structured fields, with estimate + designer filters."""
    import subprocess
    result = subprocess.run(
        [sys.executable, "scripts/run_parse.py", "all", "--source", "auctionet"],
        capture_output=False,
    )
    return result.returncode == 0


def step_triage_export():
    """Step 3: Export lots that need visual triage (downloads images, returns list)."""
    from scripts.visual_triage import export_triage_lots
    return export_triage_lots()


def show_status():
    """Show current pipeline state."""
    from backend.database import SessionLocal, init_db
    from backend.models import Lot, ParsedLotFields, LotScores

    init_db()
    db = SessionLocal()

    total = db.query(Lot).count()
    active = db.query(Lot).filter(Lot.status == "active").count()
    sold = db.query(Lot).filter(Lot.status == "sold").count()
    unsold = db.query(Lot).filter(Lot.status == "unsold").count()
    filtered = db.query(Lot).filter(Lot.status == "filtered").count()
    parsed = db.query(ParsedLotFields).count()
    scored = db.query(LotScores).count()
    needs_triage = db.query(Lot).filter(
        Lot.status == "filtered",
        Lot.visual_triage_result.is_(None),
    ).count()
    rescued = db.query(Lot).filter(
        Lot.visual_triage_result == "YES",
    ).count()

    print(f"""
Pipeline Status
═══════════════
Total lots:       {total}
Active:           {active}  (in auction, passed filters)
Sold:             {sold}  (auction ended, sold)
Unsold:           {unsold}  (auction ended, not sold)
Filtered:         {filtered}  (below threshold, not interesting)
Needs triage:     {needs_triage}  (filtered, no visual assessment yet)
Rescued by AI:    {rescued}  (visual triage YES)
Parsed fields:    {parsed}
Scored:           {scored}

Next steps:
  {'→ Run visual triage on ' + str(needs_triage) + ' lots' if needs_triage > 0 else '✓ All lots triaged'}
  {'→ Run enrichment on ' + str(active) + ' active lots' if active > scored else '✓ All lots scored'}
""")
    db.close()


async def run_pipeline(max_lots: int = 100, parse_only: bool = False, refetch_only: bool = False, min_score: int = 0):
    """Run the full pipeline."""
    if refetch_only:
        logger.info("═══ REFETCH ACTIVE LOTS ═══")
        updated = await step_refetch()
        logger.info(f"Updated {updated} lots\n")
        show_status()
        return

    if not parse_only:
        logger.info("═══ STEP 0: REFETCH ACTIVE LOTS ═══")
        updated = await step_refetch()
        logger.info(f"Updated {updated} active lots\n")

        logger.info("═══ STEP 1: FETCH NEW LOTS (pre-filter min_score={min_score}) ═══")
        fetched = await step_fetch(max_lots, min_score=min_score)
        logger.info(f"Fetched {fetched} new lots\n")

    logger.info("═══ STEP 2: PARSE + FILTER ═══")
    step_parse()

    logger.info("\n═══ STEP 3: VISUAL TRIAGE EXPORT ═══")
    triage_lots = step_triage_export()

    logger.info("\n═══ PIPELINE SUMMARY ═══")
    show_status()

    if triage_lots:
        logger.info(
            f"{len(triage_lots)} lots need visual triage. "
            f"Images in data/triage_images/. "
            f"Use Claude Code subagents to assess, then run:\n"
            f"  python scripts/visual_triage.py import LOT_ID=YES LOT_ID=NO ...\n"
            f"  python scripts/run_parse.py all --source auctionet  # re-parse rescued lots"
        )


if __name__ == "__main__":
    if "--status" in sys.argv:
        show_status()
    elif "--refetch" in sys.argv:
        asyncio.run(run_pipeline(refetch_only=True))
    elif "--parse-only" in sys.argv:
        asyncio.run(run_pipeline(parse_only=True))
    else:
        max_lots = 100
        min_score = 0
        for arg in sys.argv[1:]:
            if arg.isdigit():
                max_lots = int(arg)
            elif arg.startswith("--min-score="):
                min_score = int(arg.split("=")[1])
            elif arg == "--cream":
                min_score = 3  # Shorthand: designer-only mode
        asyncio.run(run_pipeline(max_lots, min_score=min_score))
