# auctionVision

Local-AI auction sourcing engine for Scandinavian mid-century furniture.
Scrapes Auctionet (and planned Bukowskis), enriches lots with local AI agents,
ranks by arbitrage, taste, and visual distinctiveness.

## Stack

- **Backend**: Python 3.10+, FastAPI, SQLAlchemy, SQLite, Alembic
- **Frontend**: SolidJS + Vite
- **Scraping**: Playwright + BeautifulSoup
- **Enrichment**: Local LLM agents (bounded JSON-output jobs)

## Commands

```bash
# Install backend deps
pip install -e .
pip install playwright && playwright install chromium

# Run full pipeline (scrape N lots → parse → save to SQLite)
python3 scripts/run_pipeline.py 100

# Start API (runs on http://localhost:8000)
python3 -m backend.api.main

# Start frontend (runs on http://localhost:5173)
cd frontend && npm install && npm run dev

# DB migrations
alembic upgrade head
```

## Key files

| File | Purpose |
|---|---|
| `scripts/run_pipeline.py` | Main entry point — scrape → parse → store |
| `backend/ingestion/fetcher.py` | Playwright fetcher for Auctionet |
| `backend/parsers/auctionet.py` | BeautifulSoup parser (real DOM) |
| `backend/models.py` | 12 SQLAlchemy ORM models |
| `backend/api/main.py` | FastAPI app |
| `backend/scoring.py` | Scoring engine (arbitrage, taste, wildcard) |
| `backend/importer.py` | Import enrichment JSON from agents |
| `config/designers.yaml` | Seed designers + adjacent for taste scoring |
| `config/scoring.yaml` | Scoring weights and thresholds |
| `config/norway_costs.yaml` | Norway arbitrage cost assumptions |

## Architecture

```
Playwright fetch → raw HTML snapshot → BeautifulSoup parse
→ SQLite (ParsedLotFields) → enrichment agents → LotScores
→ FastAPI views → SolidJS dashboard
```

Enrichment agents are **bounded jobs**: one input schema, one output schema, always valid JSON.

## Data

- SQLite DB: `data/auction.db`
- Raw HTML snapshots: `data/snapshots/auctionet/{date}/{lot_id}_{hash}.html`
- Rate limit: 2s between requests (~3.5 min for 100 lots)

## API views

- `GET /api/lots` — all lots with pagination
- `GET /api/views/best-buys` — top arbitrage score
- `GET /api/views/ending-soon` — ending within 2 hours
- `GET /api/views/watchlist` — starred lots

## Conventions

- Parsers are deterministic first, AI second
- All enrichment outputs validated against Pydantic schemas in `backend/schemas.py`
- Keep agent outputs as structured JSON — never free prose
- Raw snapshots are sacrosanct — don't overwrite, rerun parsers instead
- Scores live in `lot_scores` table, recalculated per `scoring_version`
