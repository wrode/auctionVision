# Auctionet Furniture Listing Crawler Implementation

## Overview

This document describes the implementation of the real Auctionet furniture listing crawler, including fetching, parsing, and database storage.

## Architecture

The implementation follows a three-stage pipeline:

1. **Fetch Stage** (`backend/ingestion/fetcher.py`): Discover listing pages and fetch raw HTML
2. **Parse Stage** (`backend/parsers/auctionet.py`): Extract structured data from HTML
3. **Storage**: Persist data to SQLite database

## Components

### 1. AuctionetFetcher (`backend/ingestion/fetcher.py`)

The `AuctionetFetcher` class handles all HTTP requests and data persistence:

#### `fetch_listing_page(page_num, category)`
- Constructs search URL: `https://auctionet.com/en/search?category={category}&page={page_num}`
- Fetches and parses HTML with BeautifulSoup
- Extracts lot URLs and IDs from listing page
- Returns list of dicts with `external_lot_id` and `lot_url`

#### `fetch_lot_detail(lot_url)`
- Fetches individual lot page
- Computes SHA256 content hash
- Saves raw HTML to disk at `data/snapshots/auctionet/{date}/{lot_id}_{hash}.html`
- Returns dict with status, hash, and file path
- Implements rate limiting to be respectful to the server

### 2. AuctionetParser (`backend/parsers/auctionet.py`)

Parses HTML using BeautifulSoup and extracts structured fields:

- **Title**: From h1 or og:title
- **Description**: From .lot-description or og:description
- **Pricing**: Current bid, estimate range, currency (SEK)
- **Condition**: From condition fields
- **Dimensions**: Extracted from description text
- **Images**: From img tags and og:image
- **Designer/Material mentions**: Via regex patterns
- **Metadata**: Auction house, seller location, time left

### 3. Database Models (`backend/models.py`)

Key tables for storing crawl results:

- **Source**: Auction source (auctionet)
- **Lot**: Individual auction item with external ID and URL
- **LotFetch**: Record of fetching a lot page (timestamp, hash, path)
- **ParsedLotFields**: Extracted structured data from lot HTML
- **LotImage**: Image URLs associated with lots

## Scripts

### `scripts/run_fetch.py`

Fetch listings and lots from Auctionet:

```bash
# Fetch 2 pages of furniture listings (default)
python scripts/run_fetch.py source auctionet --max-pages 2

# Fetch specific category for more pages
python scripts/run_fetch.py source auctionet --category furniture --max-pages 5

# Fetch a single lot
python scripts/run_fetch.py lot https://auctionet.com/en/lot/45821
```

Workflow:
1. Creates Source record if it doesn't exist
2. Calls `fetch_listing_page()` for each page
3. Creates Lot records for discovered items
4. Calls `fetch_lot_detail()` for each lot
5. Creates LotFetch record with HTML path and content hash

### `scripts/run_parse.py`

Parse fetched HTML and extract structured data:

```bash
# Parse all unparsed lots from auctionet
python scripts/run_parse.py all --source auctionet

# Parse a single lot by ID
python scripts/run_parse.py lot 45821
```

Workflow:
1. Finds unparsed LotFetch records
2. Loads raw HTML from disk
3. Runs AuctionetParser on each
4. Creates ParsedLotFields records in database

### `scripts/test_pipeline.py`

Test the complete pipeline with sample data:

```bash
# Create test data from snapshot files
python scripts/test_pipeline.py create

# Parse test data
python scripts/test_pipeline.py parse
```

## Data Flow

```
┌─────────────────────────────────────────┐
│ Fetch Listing Page (fetch_listing_page) │
│  - GET /search?category=furniture&p=1   │
│  - Parse HTML, extract lot URLs         │
│  - Returns list of {id, url}            │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ Create Lot Records (if not exists)      │
│ - Source.auctionet                      │
│ - Lot with external_id, lot_url         │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ Fetch Lot Detail (fetch_lot_detail)     │
│  - GET lot_url                          │
│  - Save HTML to snapshots/{id}_{hash}   │
│  - Compute content hash                 │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ Create LotFetch Records                 │
│ - Store path, hash, status, timestamp   │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ Parse HTML (AuctionetParser.parse)      │
│  - Load from snapshots/{id}_{hash}.html │
│  - Extract title, price, images, etc.   │
│  - Return ParsedFields                  │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ Create ParsedLotFields Records          │
│ - Store all extracted fields in DB      │
│ - Parse confidence score                │
└─────────────────────────────────────────┘
```

## Database Schema

### Source
```sql
CREATE TABLE sources (
  id INTEGER PRIMARY KEY,
  name VARCHAR(100) UNIQUE,
  base_url VARCHAR(500),
  parser_name VARCHAR(100),
  enabled INTEGER DEFAULT 1
);
```

### Lot
```sql
CREATE TABLE lots (
  id INTEGER PRIMARY KEY,
  source_id INTEGER FOREIGN KEY,
  external_lot_id VARCHAR(200),
  lot_url VARCHAR(500),
  status VARCHAR(50),
  last_fetched_at DATETIME
);
```

### LotFetch
```sql
CREATE TABLE lot_fetches (
  id INTEGER PRIMARY KEY,
  lot_id INTEGER FOREIGN KEY,
  fetched_at DATETIME,
  http_status INTEGER,
  content_hash VARCHAR(64),
  raw_html_path VARCHAR(500),
  success INTEGER
);
```

### ParsedLotFields
```sql
CREATE TABLE parsed_lot_fields (
  id INTEGER PRIMARY KEY,
  lot_id INTEGER FOREIGN KEY,
  lot_fetch_id INTEGER FOREIGN KEY,
  parser_version VARCHAR(50),
  title VARCHAR(500),
  description TEXT,
  current_bid FLOAT,
  estimate_low FLOAT,
  estimate_high FLOAT,
  currency VARCHAR(10),
  condition_text VARCHAR(200),
  dimensions_text VARCHAR(200),
  raw_designer_mentions JSON,
  raw_material_mentions JSON
);
```

## File Storage

Raw HTML snapshots are stored in a date-organized directory structure:

```
data/snapshots/
└── auctionet/
    └── 2026-03-27/
        ├── 45821_a1b2c3d4.html
        ├── 45822_e5f6g7h8.html
        └── ...
```

Filename format: `{external_lot_id}_{content_hash_first_8_chars}.html`

Benefits:
- Unique filenames prevent overwriting
- Content hash allows deduplication
- Date organization helps with archival

## Rate Limiting

The fetcher implements configurable rate limiting:

- `AUCTIONET_RATE_LIMIT_REQUESTS`: 10 requests
- `AUCTIONET_RATE_LIMIT_PERIOD`: 60 seconds
- Tracks request timestamps and sleeps if limit exceeded

## Configuration

Settings in `.env`:

```
AUCTIONET_BASE_URL=https://auctionet.com
AUCTIONET_RATE_LIMIT_REQUESTS=10
AUCTIONET_RATE_LIMIT_PERIOD=60
DATABASE_URL=sqlite:///data/auction.db
```

## Testing

The pipeline includes a test suite (`scripts/test_pipeline.py`) that:

1. Creates test data from sample HTML files
2. Verifies database record creation
3. Tests HTML parsing and field extraction
4. Validates end-to-end data flow

Sample HTML files are provided in `data/snapshots/auctionet/2026-03-27/`:
- `45821_a1b2c3d4.html`: Danish Teak Sideboard
- `45822_e5f6g7h8.html`: Eames Lounge Chair

Run tests with:
```bash
python scripts/test_pipeline.py create
python scripts/test_pipeline.py parse
```

## Error Handling

The fetcher gracefully handles:
- HTTP errors (logs and continues)
- Network timeouts (configurable timeout=30s)
- Malformed HTML (BeautifulSoup parses what it can)
- Missing files (logged and skipped)

LotFetch records store:
- HTTP status code
- Error messages
- Success flag (0 or 1)

Failed fetches can be retried by examining `LotFetch.success = 0`.

## Limitations & Future Improvements

Current limitations:
- Auctionet may have different URL patterns for different regions
- Price extraction is regex-based and may need refinement
- Image extraction could be enhanced for gallery navigation
- Designer/material extraction is heuristic-based

Future improvements:
1. Implement Selenium for JavaScript-rendered content
2. Add image downloading to `data/images/`
3. Support for pagination via JavaScript
4. More sophisticated designer/material entity linking
5. Support for multiple auction houses

## Running the Full Pipeline

```bash
# 1. Fetch fresh listings (limited to 2 pages for courtesy)
python scripts/run_fetch.py source auctionet --max-pages 2

# 2. Parse all unparsed lots
python scripts/run_parse.py all --source auctionet

# 3. Check results
python -c "
from backend.database import SessionLocal
from backend.models import Lot, ParsedLotFields
db = SessionLocal()
for lot in db.query(Lot).all():
    parsed = db.query(ParsedLotFields).filter(ParsedLotFields.lot_id == lot.id).first()
    if parsed:
        print(f'{lot.external_lot_id}: {parsed.title} - {parsed.current_bid} {parsed.currency}')
"
```

## Troubleshooting

**No lots found when fetching:**
- Check network connectivity
- Verify Auctionet URL structure (may have changed)
- Check proxy settings if in corporate environment
- Review HTML structure with browser inspector

**Parse confidence is low:**
- HTML structure may have changed
- Review extraction selectors in AuctionetParser
- Check raw_html_path in LotFetch records

**Database errors:**
- Ensure `data/` directory exists
- Check file permissions on `data/auction.db`
- Verify SQLAlchemy ORM models match schema

## Implementation Details

### Fetcher Implementation Notes

1. **URL Construction**: Auctionet uses `/en/search?category={category}&page={page_num}` pattern
2. **Lot Link Extraction**: Multiple CSS selectors tried in order:
   - `a[href*='/lot/']` - Most reliable
   - `div.lot a` - Fallback
   - `div.item a[href*='/lot/']` - Alternative
   - `li.lot a` - List format

3. **Lot ID Extraction**: From URL path `/lot/{id}` using split and parse

4. **HTML Normalization**: Converts relative URLs to absolute URLs

### Parser Implementation Notes

1. **Robust Extraction**: Uses BeautifulSoup with fallback selectors
2. **Confidence Scoring**: Default 0.7 for Auctionet (fairly consistent layout)
3. **Price Parsing**: Uses regex to extract numeric values from text
4. **Designer Detection**: Heuristic-based on capitalized words
5. **Material Detection**: Pattern matching for common materials

## Code Quality

- Type hints throughout
- Comprehensive logging
- Error handling with graceful degradation
- Database transactions with commit/rollback
- Async support for concurrent fetching (future enhancement)
