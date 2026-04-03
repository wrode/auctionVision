#!/usr/bin/env python3
"""Fetch and import Blomqvist realized prices into comparables DB.

Usage:
  python scripts/fetch_blomqvist.py              # Fetch all pages, import furniture
  python scripts/fetch_blomqvist.py --pages 3    # Limit to 3 pages
  python scripts/fetch_blomqvist.py --import-only # Import from cached JSON only
"""

import asyncio
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

sqlite3.register_adapter(dict, lambda d: json.dumps(d))
sqlite3.register_adapter(list, lambda l: json.dumps(l))

DATA_FILE = Path("data/retail_blomqvist.json")


async def fetch_and_save(max_pages: int = 7):
    """Fetch from Blomqvist and save to JSON."""
    from backend.ingestion.blomqvist import fetch_blomqvist_tilslag, filter_furniture, to_comparables

    print(f"Fetching Blomqvist tilslagsliste (up to {max_pages} pages)...")
    raw_items = await fetch_blomqvist_tilslag(max_pages=max_pages)
    print(f"  Raw items: {len(raw_items)}")

    furniture = filter_furniture(raw_items)
    print(f"  Furniture items: {len(furniture)}")

    comparables = to_comparables(furniture)
    print(f"  With prices: {len(comparables)}")

    DATA_FILE.write_text(json.dumps(comparables, ensure_ascii=False, indent=2))
    print(f"  Saved to {DATA_FILE}")

    return comparables


def import_to_db(comparables: list[dict]):
    """Import comparables into the database."""
    from backend.database import SessionLocal
    from backend.models import Comparable

    db = SessionLocal()

    # Clear old Blomqvist data to avoid duplicates
    old_count = db.query(Comparable).filter(Comparable.source_name == "Blomqvist").count()
    if old_count:
        db.query(Comparable).filter(Comparable.source_name == "Blomqvist").delete()
        db.commit()
        print(f"  Cleared {old_count} old Blomqvist records")

    count = 0
    for item in comparables:
        comp = Comparable(
            source_name=item["source_name"],
            title=item["title"][:500],
            sold_price=item["sold_price"],
            currency=item["currency"],
            country=item["country"],
            confidence=item["confidence"],
            raw_payload=item.get("raw_payload"),
        )
        db.add(comp)
        count += 1

    db.commit()
    total = db.query(Comparable).count()
    blomqvist = db.query(Comparable).filter(Comparable.source_name == "Blomqvist").count()
    print(f"  Imported {count} Blomqvist comparables")
    print(f"  Blomqvist in DB: {blomqvist}")
    print(f"  Total comparables: {total}")
    db.close()


async def main():
    import_only = "--import-only" in sys.argv
    max_pages = 7
    for i, arg in enumerate(sys.argv):
        if arg == "--pages" and i + 1 < len(sys.argv):
            max_pages = int(sys.argv[i + 1])

    if import_only:
        if not DATA_FILE.exists():
            print(f"No cached data at {DATA_FILE}")
            return
        comparables = json.loads(DATA_FILE.read_text())
    else:
        comparables = await fetch_and_save(max_pages)

    print(f"\nImporting {len(comparables)} comparables...")
    import_to_db(comparables)
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
