#!/usr/bin/env python3
"""Run the arbitrage agent on all lots with parsed fields.

Updates lot_scores.explanation_json with comparables-based value estimates.
"""

import asyncio
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

sqlite3.register_adapter(dict, lambda d: json.dumps(d))
sqlite3.register_adapter(list, lambda l: json.dumps(l))

from backend.database import SessionLocal
from backend.enrichment.arbitrage import ArbitrageAgent
from backend.models import Lot, LotScores, ParsedLotFields


# Categories to skip (not resellable furniture)
SKIP_CATEGORIES = {"books", "toys", "miniatures", "dolls", "reference"}


async def main():
    db = SessionLocal()
    agent = ArbitrageAgent()

    # Get all lots with parsed fields
    parsed_lots = db.query(ParsedLotFields).all()
    lot_map = {}
    for p in parsed_lots:
        if p.lot_id not in lot_map or (p.created_at and lot_map[p.lot_id].created_at and p.created_at > lot_map[p.lot_id].created_at):
            lot_map[p.lot_id] = p

    processed = 0
    skipped = 0
    errors = 0

    for lot_id, parsed in sorted(lot_map.items()):
        # Skip non-furniture categories
        cat = (parsed.category_raw or "").lower()
        if any(skip in cat for skip in SKIP_CATEGORIES):
            skipped += 1
            continue

        try:
            input_data = {
                "current_bid": parsed.current_bid,
                "estimate_low": parsed.estimate_low,
                "estimate_high": parsed.estimate_high,
                "currency": parsed.currency or "SEK",
                "object_type": parsed.category_raw,
            }

            result = await agent.run(lot_id, input_data, db)

            # Update or create lot_scores with the arbitrage output
            scores = db.query(LotScores).filter(LotScores.lot_id == lot_id).first()
            if not scores:
                scores = LotScores(lot_id=lot_id, scoring_version="v2")

            # Rebuild explanation_json (force new dict for SQLAlchemy mutation detection)
            existing = dict(scores.explanation_json or {})
            existing["arbitrage_output"] = result
            existing["ai_value_low"] = result.get("ai_value_low")
            existing["ai_value_high"] = result.get("ai_value_high")
            existing["ai_value_basis"] = result.get("ai_value_basis")
            existing["comparables_count"] = result.get("comparables_count")
            existing["retail_new_price"] = result.get("retail_new_price")
            scores.explanation_json = existing

            # Set arbitrage score
            scores.arbitrage_score = result.get("arbitrage_score")
            scores.resale_arb_score = result.get("arbitrage_score")

            db.add(scores)
            db.commit()
            processed += 1

            comp_count = result.get("comparables_count", 0)
            resale = result.get("expected_resale_value")
            if processed % 20 == 0 or processed <= 5:
                title = (parsed.title or "")[:50]
                print(f"  [{processed}] Lot {lot_id}: {title}… comps={comp_count} resale={resale}")

        except Exception as e:
            errors += 1
            print(f"  ERROR lot {lot_id}: {e}")
            db.rollback()

    db.close()
    print(f"\nDone: {processed} processed, {skipped} skipped (non-furniture), {errors} errors")


if __name__ == "__main__":
    asyncio.run(main())
