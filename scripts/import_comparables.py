#!/usr/bin/env python3
"""Import comparables from research and comp data files into the database.

Reads:
  - data/research/*.json  (comparables arrays with platform, price, currency, etc.)
  - data/comp_*.json      (detailed comp files with different format)
  - data/enrichments/*.json (for object_type, materials, country metadata)

Populates:
  - entities table (designers/manufacturers from enrichment data)
  - comparables table (all comparable sales/listings)
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, event
from backend.database import SessionLocal, engine
from backend.models import Comparable, Entity


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RESEARCH_DIR = DATA_DIR / "research"
ENRICHMENTS_DIR = DATA_DIR / "enrichments"


# Enable JSON serialization for SQLite
@event.listens_for(engine, "connect")
def _set_sqlite_json(dbapi_conn, connection_record):
    import sqlite3
    sqlite3.register_adapter(dict, lambda d: json.dumps(d))
    sqlite3.register_adapter(list, lambda l: json.dumps(l))


def load_enrichment_metadata() -> dict[str, dict]:
    """Load enrichment files to get object_type, materials, country per lot."""
    metadata = {}
    if not ENRICHMENTS_DIR.exists():
        return metadata

    for f in ENRICHMENTS_DIR.iterdir():
        if not f.name.endswith(".json") or f.name.startswith("_"):
            continue
        try:
            data = json.loads(f.read_text())
            lot_id = data.get("lot_id") or f.stem
            # Normalize materials: can be list of strings or list of dicts
            raw_materials = data.get("materials", [])
            if raw_materials and isinstance(raw_materials[0], dict):
                materials = [m.get("material", m.get("name", str(m))) for m in raw_materials]
            else:
                materials = [str(m) for m in raw_materials] if raw_materials else []

            # Normalize country: can be string or dict
            raw_country = data.get("country_of_origin")
            if isinstance(raw_country, dict):
                country = raw_country.get("stated") or raw_country.get("name") or str(raw_country)
            else:
                country = str(raw_country) if raw_country else None

            metadata[str(lot_id)] = {
                "object_type": data.get("object_type"),
                "materials": materials,
                "country": country,
                "designer": data.get("designer", {}).get("name") if isinstance(data.get("designer"), dict) else None,
                "manufacturer": data.get("manufacturer", {}).get("name") if isinstance(data.get("manufacturer"), dict) else None,
            }
        except (json.JSONDecodeError, Exception) as e:
            print(f"  Warning: skipping enrichment {f.name}: {e}")
    return metadata


def extract_platform_from_url(url: str) -> str:
    """Extract platform name from URL."""
    try:
        host = urlparse(url).hostname or ""
        host = host.replace("www.", "")
        platform_map = {
            "1stdibs.com": "1stDibs",
            "pamono.com": "Pamono",
            "pamono.eu": "Pamono",
            "barnebys.com": "Barnebys",
            "mutualart.com": "MutualArt",
            "lauritz.com": "Lauritz",
            "bruun-rasmussen.dk": "Bruun Rasmussen",
            "bukowskis.com": "Bukowskis",
            "stockholms-auktionsverk.se": "Stockholms Auktionsverk",
            "christies.com": "Christie's",
            "sothebys.com": "Sotheby's",
            "phillips.com": "Phillips",
            "bonhams.com": "Bonhams",
            "wright20.com": "Wright",
            "rfrago.com": "Rago/Wright",
            "vinterior.co": "Vinterior",
            "chairish.com": "Chairish",
            "ebay.com": "eBay",
            "ebay.co.uk": "eBay UK",
            "catawiki.com": "Catawiki",
            "gumtree.com": "Gumtree UK",
            "etsy.com": "Etsy",
            "selency.com": "Selency",
            "design-market.fr": "Design Market",
            "finn.no": "Finn.no",
        }
        for domain, name in platform_map.items():
            if domain in host:
                return name
        # Fallback: use domain stem
        return host.split(".")[0].capitalize() if host else "Unknown"
    except Exception:
        return "Unknown"


def parse_date(date_str: str | None) -> datetime | None:
    """Try to parse a date string into datetime."""
    if not date_str:
        return None
    date_str = str(date_str).strip()
    # Skip non-date strings
    if any(x in date_str.lower() for x in ["unknown", "not specified", "sold", "n/a", "current"]):
        return None
    for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y"]:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def import_entities(db, enrichment_metadata: dict[str, dict]) -> dict[str, int]:
    """Create entities from enrichment metadata. Returns name->id mapping."""
    entity_map = {}
    seen = set()

    for lot_id, meta in enrichment_metadata.items():
        for name, etype in [(meta.get("designer"), "designer"), (meta.get("manufacturer"), "manufacturer")]:
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())

            existing = db.query(Entity).filter(
                func.lower(Entity.canonical_name) == name.lower()
            ).first()

            if existing:
                entity_map[name.lower()] = existing.id
            else:
                entity = Entity(
                    entity_type=etype,
                    canonical_name=name,
                    country=meta.get("country"),
                )
                db.add(entity)
                db.flush()
                entity_map[name.lower()] = entity.id

    db.commit()
    print(f"  Entities: {len(entity_map)} created/found")
    return entity_map


def import_research_comparables(db, entity_map: dict[str, int], enrichment_metadata: dict[str, dict]) -> int:
    """Import comparables from data/research/*.json files."""
    count = 0
    if not RESEARCH_DIR.exists():
        return count

    for f in sorted(RESEARCH_DIR.iterdir()):
        if not f.name.endswith(".json") or f.name.startswith("_"):
            continue

        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, Exception):
            continue

        lot_id = str(data.get("lot_id") or f.stem)
        comps = data.get("comparables", [])
        meta = enrichment_metadata.get(lot_id, {})

        for comp in comps:
            # Extract source info
            url = comp.get("source", "")
            platform = comp.get("platform") or extract_platform_from_url(url)
            description = comp.get("description", "")

            comparable = Comparable(
                source_name=platform,
                external_ref=url if url.startswith("http") else None,
                title=description[:500] if description else f"Comparable for lot {lot_id}",
                object_type=meta.get("object_type"),
                material_tags=meta.get("materials") if meta.get("materials") else None,
                sold_price=comp.get("price"),
                currency=comp.get("currency", "EUR"),
                sold_at=parse_date(comp.get("date")),
                country=meta.get("country"),
                confidence=_relevance_to_confidence(comp.get("relevance", "")),
                raw_payload={**comp, "lot_id": lot_id},
            )

            # Link to entity if we can match designer
            designer = meta.get("designer")
            if designer and designer.lower() in entity_map:
                comparable.entity_id = entity_map[designer.lower()]

            db.add(comparable)
            count += 1

    db.commit()
    return count


def import_comp_files(db, entity_map: dict[str, int], enrichment_metadata: dict[str, dict]) -> int:
    """Import comparables from data/comp_*.json files (different format)."""
    count = 0

    for f in sorted(DATA_DIR.glob("comp_*.json")):
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, Exception):
            continue

        lot_id = str(data.get("lot_id") or f.stem.replace("comp_", ""))
        comps = data.get("comparables", [])
        meta = enrichment_metadata.get(lot_id, {})

        for comp in comps:
            source = comp.get("source", "Unknown")
            title = comp.get("title", "")

            # Pick the best price/currency from price_eur > price_gbp > price_usd
            price, currency = None, None
            if comp.get("price_eur"):
                price, currency = comp["price_eur"], "EUR"
            elif comp.get("price_gbp"):
                price, currency = comp["price_gbp"], "GBP"
            elif comp.get("price_usd"):
                price, currency = comp["price_usd"], "USD"

            comparable = Comparable(
                source_name=source,
                external_ref=comp.get("url"),
                title=title[:500] if title else f"Comparable for lot {lot_id}",
                object_type=meta.get("object_type"),
                material_tags=meta.get("materials") if meta.get("materials") else None,
                sold_price=price,
                currency=currency,
                sold_at=parse_date(comp.get("date")),
                country=comp.get("location"),
                confidence=_type_to_confidence(comp.get("type", "")),
                raw_payload={**comp, "lot_id": lot_id},
            )

            designer = meta.get("designer")
            if designer and designer.lower() in entity_map:
                comparable.entity_id = entity_map[designer.lower()]

            db.add(comparable)
            count += 1

    db.commit()
    return count


def _relevance_to_confidence(relevance: str) -> float:
    """Convert relevance description to confidence score."""
    r = relevance.lower() if relevance else ""
    if r.startswith("high"):
        return 0.9
    elif r.startswith("medium-high"):
        return 0.75
    elif r.startswith("medium"):
        return 0.6
    elif r.startswith("low"):
        return 0.3
    return 0.5


def _type_to_confidence(price_type: str) -> float:
    """Convert price type to confidence score."""
    t = price_type.lower() if price_type else ""
    if "hammer" in t:
        return 0.95  # Actual auction results are most reliable
    elif "dealer_retail_sold" in t:
        return 0.8
    elif "asking" in t:
        return 0.6  # Asking prices aren't final
    elif "dealer_retail" in t:
        return 0.5
    elif "new_retail" in t:
        return 0.4  # Reference only
    return 0.5


def main():
    print("Loading enrichment metadata...")
    enrichment_metadata = load_enrichment_metadata()
    print(f"  Loaded metadata for {len(enrichment_metadata)} lots")

    db = SessionLocal()
    try:
        print("\nImporting entities...")
        entity_map = import_entities(db, enrichment_metadata)

        print("\nImporting research comparables...")
        research_count = import_research_comparables(db, entity_map, enrichment_metadata)
        print(f"  Imported {research_count} from research files")

        print("\nImporting comp file comparables...")
        comp_count = import_comp_files(db, entity_map, enrichment_metadata)
        print(f"  Imported {comp_count} from comp files")

        total = db.query(Comparable).count()
        entity_total = db.query(Entity).count()
        print(f"\n--- Done ---")
        print(f"Total comparables in DB: {total}")
        print(f"Total entities in DB: {entity_total}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
