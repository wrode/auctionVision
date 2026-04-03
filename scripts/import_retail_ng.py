#!/usr/bin/env python3
"""Import Nordiska Galleriet retail pricing data into comparables DB.

Reads the extracted JSON data and imports as retail comparables with
source_name = 'Nordiska Galleriet'.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3
# Register JSON adapters before importing SQLAlchemy
sqlite3.register_adapter(dict, lambda d: json.dumps(d))
sqlite3.register_adapter(list, lambda l: json.dumps(l))

from backend.database import SessionLocal
from backend.models import Comparable, Entity

# NOK to EUR approximate rate (April 2026)
NOK_EUR = 0.085

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "retail_nordiska_galleriet.json"


def classify_object_type(title: str, slug: str) -> str:
    """Infer object type from product title."""
    t = title.lower()
    if any(w in t for w in ['stol', 'chair', 'spisestol']):
        if 'barkrakk' in t or 'barstol' in t or 'bar' in t:
            return 'barstool'
        if 'kontorstol' in t:
            return 'office chair'
        if 'lenestol' in t or 'armchair' in t or 'wing' in t:
            return 'armchair'
        if 'gyngestol' in t:
            return 'rocking chair'
        return 'dining chair'
    if any(w in t for w in ['sofa', 'seter']):
        return 'sofa'
    if any(w in t for w in ['spisebord', 'dining table']):
        return 'dining table'
    if any(w in t for w in ['salongbord', 'coffee table', 'sidebord']):
        return 'coffee table'
    if any(w in t for w in ['hylle', 'shelf', 'hyllsystem', 'hyllesystem']):
        return 'wall-mounted shelving system'
    if any(w in t for w in ['skap', 'skjenk', 'sideboard', 'kommode', 'cabinet', 'drawer']):
        return 'sideboard'
    if any(w in t for w in ['benk', 'bench']):
        return 'bench'
    if any(w in t for w in ['krakk', 'stool', 'fotskammel', 'puff']):
        return 'stool'
    if any(w in t for w in ['skrivebord', 'desk']):
        return 'desk'
    if any(w in t for w in ['bord', 'table']):
        return 'table'
    if any(w in t for w in ['lampe', 'pendel', 'belysning', 'light']):
        return 'lighting'
    if any(w in t for w in ['solseng', 'lounger']):
        return 'lounger'
    if any(w in t for w in ['speil', 'mirror']):
        return 'mirror'
    return 'furniture'


def infer_designer(brand: str, title: str, page_designer: str) -> str | None:
    """Try to map to a known designer from the product context."""
    t = (brand + ' ' + title).lower()
    # Direct designer attribution from title patterns
    if 'mogensen' in t or 'bm' in t.split()[0:2]:
        return 'Børge Mogensen'
    if 'wegner' in t or t.startswith('ch') or 'y-stol' in t or 'y stol' in t:
        return 'Hans J. Wegner'
    if 'jacobsen' in t or 'egget' in t or 'svanen' in t or 'myren' in t or 'syveren' in t or 'drop' in t:
        return 'Arne Jacobsen'
    if 'ditzel' in t or 'trinidad' in t:
        return 'Nanna Ditzel'
    if 'panton' in t:
        return 'Verner Panton'
    if 'kjærholm' in t or t.startswith('pk'):
        return 'Poul Kjærholm'
    if 'string' in brand.lower():
        return 'Kajsa & Nisse Strinning'
    # Fall back to page designer if it's a real designer (not a brand page)
    if page_designer in ['Børge Mogensen', 'Poul Henningsen', 'Hans J. Wegner', 'Arne Jacobsen']:
        return page_designer
    return None


def main():
    if not DATA_FILE.exists():
        print(f"Data file not found: {DATA_FILE}")
        return

    with open(DATA_FILE) as f:
        all_data = json.load(f)

    db = SessionLocal()
    count = 0
    skipped = 0

    try:
        for page in all_data:
            page_designer = page['designer']
            items = page['items']

            for item in items:
                title = item['title']
                price_nok = item.get('price_nok')
                brand = item.get('brand', '')
                slug = item.get('slug', '')

                if not price_nok or price_nok < 100:
                    skipped += 1
                    continue

                # Skip non-furniture items (cutlery, cushions, etc.)
                tl = title.lower()
                if any(w in tl for w in ['bestikk', 'cutlery', 'teskje', 'spoon', 'fork', 'sett med', 'parasoll', 'pute til', 'sittepute', 'setepute', 'klesstativ', 'kleshenger']):
                    skipped += 1
                    continue

                price_eur = round(price_nok * NOK_EUR)
                obj_type = classify_object_type(title, slug)
                designer = infer_designer(brand, title, page_designer)

                # Link to entity if possible
                entity_id = None
                if designer:
                    from sqlalchemy import func
                    entity = db.query(Entity).filter(
                        func.lower(Entity.canonical_name) == designer.lower()
                    ).first()
                    if entity:
                        entity_id = entity.id

                comp = Comparable(
                    source_name='Nordiska Galleriet',
                    external_ref=f"https://www.nordiskagalleriet.no{slug}" if slug else None,
                    title=f"{brand} {title}".strip()[:500],
                    object_type=obj_type,
                    material_tags=None,
                    sold_price=price_eur,
                    currency='EUR',
                    sold_at=None,  # Current retail price, not a sale date
                    country='Norway',
                    confidence=0.95,  # High confidence - actual retail price
                    raw_payload={
                        'brand': brand,
                        'title': title,
                        'price_nok': price_nok,
                        'price_eur': price_eur,
                        'slug': slug,
                        'source_page': page_designer,
                        'price_type': 'new_retail',
                        'scraped_date': '2026-04-01',
                    },
                    entity_id=entity_id,
                )
                db.add(comp)
                count += 1

        db.commit()
        total = db.query(Comparable).count()
        ng_count = db.query(Comparable).filter(Comparable.source_name == 'Nordiska Galleriet').count()
        print(f"Imported {count} retail comparables from Nordiska Galleriet (skipped {skipped})")
        print(f"NG comparables in DB: {ng_count}")
        print(f"Total comparables in DB: {total}")

    finally:
        db.close()


if __name__ == '__main__':
    main()
