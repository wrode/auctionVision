# Handover: Local Playwright Scrape → Full Pipeline

## What's done

The full repo is scaffolded and committed. SQLite schema (12 tables) is migrated. FastAPI backend runs. SolidJS frontend scaffolded. Parser rewritten for real Auctionet DOM. Everything is wired up — just needs data.

The VM sandbox blocks both outbound HTTP and Playwright process spawning, so scraping must run on the host Mac.

## What to run

```bash
cd ~/path-to/auctionVision   # wherever the repo is mounted

# 1. Install deps (if not already)
pip install -e .
pip install playwright
playwright install chromium

# 2. Run the pipeline — scrapes 100 lots, parses, saves to SQLite
python3 scripts/run_pipeline.py 100

# 3. Start the API
python3 -m backend.api.main &

# 4. Start the frontend
cd frontend && npm install && npm run dev
```

`run_pipeline.py` does everything: fetches 3 listing pages via Playwright, takes the first 100 lot URLs, visits each detail page, saves raw HTML snapshots to `data/snapshots/auctionet/{date}/`, parses each with BeautifulSoup, and writes Source, Lot, LotFetch, LotImage, and ParsedLotFields records into SQLite.

## Auctionet site structure (verified by manual browser inspection)

### URL patterns
- **Listing/search:** `https://auctionet.com/en/search?q=furniture&page={n}` — ~47 lots per page, 121 pages total (~5,785 active furniture items)
- **Lot detail:** `https://auctionet.com/en/{numeric_id}-{slug}` — NOT `/lot/{id}`
- **Images:** `https://images.auctionet.com/thumbs/large_item_{id}_{hash}.jpg`

### Listing page HTML
- Lot links are `<a href="/en/{id}-{slug}">` scattered across the page
- Extract lot IDs via regex: `/en/(\d+)-`
- Each card area has: title, time remaining ("9 days"), bid count, price ("126 EUR")
- Deduplicate by ID (same lot appears in multiple `<a>` tags)

### Detail page HTML — all sections use `<h2>` headings

| Field | DOM location |
|---|---|
| **Title** | `<h1>` — strip leading lot number like `5001970.` via `re.sub(r"^\d+\.\s*", "", text)` |
| **Subtitle/subcategory** | `<title>` tag — format: `"TITLE. Category - Subcategory - Auctionet"` — split on ` - Auctionet`, take last part |
| **Description** | `<h2>Description</h2>` → next sibling `<div>` — contains materials, dimensions, manufacturer |
| **Condition** | `<h2>Condition</h2>` → next sibling `<p>` |
| **Designer** | `<h2>Artist/designer</h2>` → next sibling `<p>` — e.g. `"Poul Henningsen (1894–1967)"`, `"Børge Mogensen (1914–1972)"` |
| **Resale right** | `<h2>Resale right</h2>` → next sibling `<p>` — "No" or "Yes" |
| **Current bid** | Text pattern: `Highest bid\s*\n?\s*(\d+)\s*EUR` — or `"No bids"` → null |
| **Estimate** | Text pattern: `Estimate:\s*(\d+)\s*EUR` — set both low and high to same value |
| **Min bid** | Text pattern: `Minimum bid:\s*(\d+)\s*EUR` |
| **End time** | Text pattern: `(\d{1,2}\s+\w{3}\s+\d{4}\s+at\s+\d{1,2}:\d{2}\s*\w*)` — e.g. `"3 Apr 2026 at 21:24 CEST"` |
| **Time remaining** | Text pattern: `Ends in\s*\n?\s*(\d+\s+\w+)` — e.g. `"7 days"`, `"21 hours"` |
| **Location** | Text pattern: `Item is located in\s+([^\n]+)` — e.g. `"Malmö, Sweden"` |
| **House** | Text pattern: `House\s*\n\s*([^\n]+)` — e.g. `"Crafoord Auktioner Malmö"` |
| **Categories** | Breadcrumb links containing known values: `Furniture`, `Armchairs & Chairs`, `Coffee Tables`, `Sofas`, `Tables`, `Sideboards`, etc. |
| **Images** | `<img>` tags where src contains `item_` — prefer `large_` prefix. Also check `<meta property="og:image">` |
| **Dimensions** | Regex from description: `((?:Length\|Height\|Width\|Depth\|Diameter).*?(?:cm\|mm))` |
| **Materials** | Regex from description: `leather`, `wood`, `teak`, `oak`, `mahogany`, `walnut`, `steel`, `chrome`, `brass`, `glass`, `marble`, `fabric` etc. |
| **Designer mentions** | Regex: `([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+\(\d{4}[–-]\d{4}\)` for names with birth/death years |

### Currency note
Auctionet displays prices in EUR but converts bids to SEK internally. Our parser stores EUR as the currency.

### Sample extracted data (verified)

```json
{
  "id": "5001970",
  "title": "BØRGE MOGENSEN. A sofa, model 2212, Fredericia Furniture, Denmark.",
  "description": "Loose padded cushions upholstered in brown leather. Length 158, depth 81, height 76 cm.",
  "condition": "Normal wear and tear, scratches and scratch marks, legs with stains.",
  "designer": "Børge Mogensen (1914–1972)",
  "estimate": 552,
  "current_bid": null,
  "currency": "EUR",
  "end_time": "3 Apr 2026 at 21:24 CEST",
  "location": "Malmö, Sweden",
  "house": "Crafoord Auktioner Malmö",
  "categories": ["Furniture", "Coffee Tables"],
  "images": [
    "https://images.auctionet.com/thumbs/large_item_5001970_d165a8d953.jpg",
    "https://images.auctionet.com/thumbs/large_item_5001970_607a0b5658.jpg"
  ]
}
```

```json
{
  "id": "5006656",
  "title": "POUL HENNINGSEN. Chair, PH-Stolen, no 258, PH Furniture/Toneart, Denmark.",
  "description": "Stainless tube, black upholstery, armrests wrapped with leather cord.\nHeight 68, seat height 46, width 52 cm.",
  "condition": "Minor wear and tear.",
  "designer": "Poul Henningsen (1894–1967)",
  "estimate": 276,
  "current_bid": null,
  "currency": "EUR",
  "end_time": "6 Apr 2026 at 13:01 CEST",
  "location": "Växjö, Sweden",
  "house": "Växjö Auktionskammare",
  "categories": ["Furniture", "Armchairs & Chairs"],
  "images": [
    "https://images.auctionet.com/thumbs/large_item_5006656_736fdd0715.jpg",
    "https://images.auctionet.com/thumbs/large_item_5006656_208a8ab579.jpg"
  ]
}
```

## Key files

| File | Purpose |
|---|---|
| `scripts/run_pipeline.py` | **Main entry point** — fetches N lots via Playwright, parses, saves to SQLite |
| `backend/ingestion/fetcher.py` | `AuctionetFetcher` — Playwright-based, handles listing + detail pages |
| `backend/parsers/auctionet.py` | `AuctionetParser` v2 — BeautifulSoup parser matching real DOM above |
| `backend/parsers/base.py` | `ParsedFields` dataclass, `BaseParser` ABC |
| `backend/models.py` | 12 SQLAlchemy ORM models |
| `backend/database.py` | Engine, SessionLocal, init_db() |
| `backend/api/main.py` | FastAPI app — `python -m backend.api.main` |
| `backend/importer.py` | JSON import for Claude-produced enrichment/comparables |
| `config/designers.yaml` | 14 seed designers + 9 adjacent for taste scoring |
| `config/scoring.yaml` | Scoring weights and thresholds |
| `config/norway_costs.yaml` | Norway arbitrage assumptions (shipping, toll, MVA) |

## Rate limiting

The fetcher has a 2-second sleep between requests. For 100 lots across 3 listing pages: ~3 listing fetches + ~100 detail fetches = ~103 requests × 2s = ~3.5 minutes. Adjust the sleep in `fetcher.py` `_apply_rate_limit()` if needed.

## After scraping

Once SQLite has data, the API views will return real lots:
- `GET /api/views/best-buys` — top lots by arbitrage score (will be empty until enrichment runs)
- `GET /api/views/ending-soon` — lots ending within 2 hours, sorted by end time
- `GET /api/views/watchlist` — lots the user has starred
- `GET /api/lots` — all lots with pagination

For the views that depend on scores (best-buys, norway-arbitrage, taste, wildcards), those need enrichment runs. The enrichment stubs are in `backend/enrichment/`. The ending-soon and watchlist views work immediately with just parsed data.

To get scores populated quickly, run the basic scoring engine which uses parsed fields only (no Claude enrichment needed):
```python
from backend.scoring import compute_lot_scores
from backend.database import SessionLocal
db = SessionLocal()
# Score all lots
from backend.models import Lot
for lot in db.query(Lot).all():
    compute_lot_scores(db, lot.id)
db.close()
```

## Unresolved: enrichment writeback

The Claude skill reads snapshots from `data/snapshots/`, outputs structured JSON matching the schemas in `backend/schemas.py`, and then:
```bash
# Import enrichment results
python3 -c "
from backend.importer import import_enrichment_json
import_enrichment_json(lot_id=123, agent_name='attribution', json_path='path/to/output.json')
"

# Import comparables
python3 -c "
from backend.importer import import_comparables_json
import_comparables_json('path/to/comparables.json')
"
```
