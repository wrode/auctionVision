# Local-AI Auction Sourcing Engine — MVP Spec

## Purpose

Build an MVP that ingests listings from selected auction sites, stores raw source snapshots, enriches each lot using local AI agents, and ranks objects by buy-side opportunity.

The system is designed to help identify underpriced objects worth buying, with a specific emphasis on Scandinavian mid-century and modernist furniture, lighting, and related design objects.

This spec is written for an implementation agent. It should be sufficient to begin scaffolding the repository and first-pass services.

---

## Core Product Goal

Find lots worth buying before other buyers notice them.

The MVP should surface opportunities across three distinct alpha streams:

1. **Known Designer / Brand Arbitrage**
   - Identify lots tied to known designers, brands, or workshops.
   - Compare listing price against expected market value.
   - Flag cases where current bid or estimate appears meaningfully below fair value.
   - Explicitly model Sweden-to-Norway value gaps.

2. **Adjacent Taste Discovery**
   - Start from a seed set of liked designers and object types.
   - Suggest similar or adjacent designers, producers, and forms.
   - Learn from stars, skips, and clicks over time.

3. **Visual Wild Cards**
   - Identify objects that are visually striking, sculptural, rare-looking, or unusually luxurious.
   - Support manual curation in addition to image-based scoring.

---

## Initial Target Sources

- Auctionet
- Bukowskis

The system should be built so additional sources can be added later.

---

## Guiding Principles

- Use **deterministic parsing first**, AI second.
- Use **local AI runs** for enrichment and reasoning.
- Store **raw source snapshots** so analysis can be rerun without scraping again.
- Prefer **structured JSON outputs** from agents over long prose.
- Treat the three alpha streams as **separate models**, not one blended score at first.
- Build for **human-in-the-loop sourcing**, not autonomous buying.

---

## Answer to the HTML Snapshot Question

Yes: raw HTML should be captured **per fetch run**.

For each lot fetch:
- save the raw HTML snapshot returned at that time
- extract normalized fields from that snapshot
- store the fetch timestamp and parser/enrichment versions

This makes the system auditable and allows:
- rerunning parsers
- rerunning AI enrichment
- comparing field changes over time
- debugging extraction issues
- tracking dynamic auction changes near closing

Recommended approach:
- store one raw snapshot per fetch event
- deduplicate only if content hash is identical
- keep a `content_hash` for change detection

---

## MVP Scope

### In Scope

- Fetch listings from Auctionet and Bukowskis
- Save raw listing snapshots and parsed fields
- Normalize designers, brands, object types, materials, and eras
- Run local AI enrichment jobs
- Rank lots by:
  - arbitrage potential
  - Norway premium potential
  - taste adjacency
  - visual distinctiveness
- Show ranked lots in a simple internal dashboard
- Allow starring, skipping, and adding to watchlist
- Re-fetch watched or time-sensitive lots on a schedule
- Show rationale and risks for each surfaced lot

### Out of Scope for MVP

- Automated bidding
- Full mobile app
- Multi-user support
- Real-time websocket architecture
- Payment flows
- Public-facing marketplace
- Fully autonomous agent loops
- End-to-end resale automation
- Advanced image embedding infra unless needed later

---

## Functional Requirements

### 1. Ingestion

The system must:
- fetch source listing pages
- fetch lot detail pages
- extract obvious structured fields
- store raw HTML snapshots for each fetch
- download and store image URLs and optionally local image copies
- support scheduled refreshes
- support accelerated refresh for ending-soon watched lots

### 2. Parsing

The parser must attempt to extract:
- source
- lot_id
- lot_url
- title
- subtitle if available
- description
- current_bid
- estimate_low
- estimate_high
- currency
- buyer_premium if visible or known from source config
- auction_end_time
- time_left_text
- category
- condition_text
- dimensions_text
- maker/designer text mentions
- provenance text
- image_urls
- auction_house / seller / location if available

The parser should be deterministic and resilient to partial field absence.

### 3. Normalization

The system must normalize:
- designer names
- brands / producers / manufacturers
- object types
- materials
- eras / decades
- currencies

Examples:
- "Arne Jacobsen", "Jacobsen", "Arne Jacobsen attributed to" should map into canonicalized entities plus confidence flags.
- "easy chair", "lounge chair", "armchair" should normalize into a canonical object taxonomy where useful.

### 4. Local AI Enrichment

Each lot should be processed by distinct local enrichment jobs.

#### 4A. Attribution Agent
Purpose:
- infer likely designer / brand / producer / object type / era / materials
- produce confidence
- identify ambiguity and risk

Input:
- parsed text fields
- category
- dimensions
- condition text

Output example:
```json
{
  "designer_candidate": "Ingmar Relling",
  "designer_confidence": 0.71,
  "producer_candidate": null,
  "object_type": "lounge chair",
  "era": "1960s",
  "materials": ["wood", "leather"],
  "attribution_flags": ["not_explicitly_attributed"],
  "risk_flags": ["attribution_ambiguous"]
}
```

#### 4B. Arbitrage Agent
Purpose:
- estimate fair market range
- estimate Norway resale potential
- compute attractiveness after costs
- explain why a lot may be underpriced

Input:
- parsed lot fields
- normalized fields
- attribution output
- comp results
- fee assumptions
- shipping/restoration assumptions

Output example:
```json
{
  "fair_value_range_source_currency": [12000, 18000],
  "expected_norway_value": [18000, 26000],
  "landed_cost_estimate": 9000,
  "estimated_margin_range": [3000, 12000],
  "arbitrage_score": 0.82,
  "confidence": 0.64,
  "reasons": [
    "Current bid is materially below comparable range",
    "Designer/style fit is commercially attractive in Norway"
  ],
  "risks": [
    "Medium attribution confidence",
    "Possible upholstery or restoration risk"
  ]
}
```

#### 4C. Taste / Adjacency Agent
Purpose:
- score fit against seed taste profile
- suggest adjacent designers or categories
- determine whether a lot is in-lane or exploratory

Input:
- seed designers
- user action history
- normalized lot fields
- attribution output

Output example:
```json
{
  "taste_score": 0.77,
  "mode": "adjacent",
  "similar_to": ["Finn Juhl", "Hans Wegner"],
  "adjacent_entities": ["Ole Wanscher", "Ib Kofod-Larsen"],
  "reasons": [
    "Shares low, sculptural Danish modern language",
    "Material and era align with starred history"
  ]
}
```

#### 4D. Visual Wild-Card Agent
Purpose:
- identify visually exceptional objects
- score unusualness and room presence
- support the “rich man's living room” lane

Input:
- primary listing image(s)
- optional parsed text

Output example:
```json
{
  "wildcard_score": 0.69,
  "sculptural_score": 0.78,
  "luxury_material_score": 0.54,
  "distinctiveness_score": 0.73,
  "reasons": [
    "Bold silhouette",
    "Uncommon material combination",
    "Visually dominant form"
  ],
  "risks": [
    "Commercial liquidity unclear"
  ]
}
```

### 5. Ranking

The UI should expose separate ranked views.

Required views:
- Best Buys
- Norway Arbitrage
- Your Taste
- Wild Cards
- Ending Soon
- Watchlist

A lot may appear in multiple views.

### 6. User Actions

The MVP should support:
- star lot
- skip lot
- watch lot
- archive lot
- add note
- mark bought
- mark false positive

These actions should feed later model tuning.

### 7. Monitoring / Refresh

The system should refresh lots using different cadences.

Suggested policy:
- new broad ingest: every 30–120 minutes
- active high-score lots: every 15–30 minutes
- watched lots ending within 2 hours: every 5–10 minutes
- watched lots ending very soon: every 20–60 seconds if operationally safe

The cadence logic should be configurable per source.

---

## Non-Functional Requirements

- All enrichment should be rerunnable.
- All outputs must be versioned.
- Raw data and enrichments must be auditable.
- Failures in one agent must not block the entire pipeline.
- Parsing and enrichment should be idempotent where possible.
- Source-specific parsing logic must be isolated.
- Every important score should have an explanation and risk flags.
- The system should remain usable if one agent is disabled.

---

## Repository Structure

Suggested structure:

```text
repo/
  README.md
  spec.md
  .env.example
  pyproject.toml
  docker-compose.yml

  apps/
    api/
    worker/
    web/

  packages/
    core/
    parsers/
    enrichers/
    ranking/
    db/
    config/

  data/
    raw/
    snapshots/
    fixtures/

  scripts/
    backfill.py
    run_fetch.py
    run_parse.py
    run_enrich.py

  docs/
    architecture.md
    prompts/
```

Alternative: collapse into a monorepo with `backend/` and `frontend/` if implementation speed is more important than package purity.

---

## Suggested Tech Stack

### Backend
- Python 3.11+
- FastAPI for internal API
- SQLAlchemy or SQLModel
- Alembic for migrations
- Pydantic for schemas

### Scraping / Fetching
- Playwright for browser-driven fetches when needed
- `httpx` / `requests` for cheaper fetches when pages are straightforward
- BeautifulSoup / lxml for parsing

### Database
- PostgreSQL

### Queue / Jobs
MVP options:
- APScheduler + DB-backed job table
- RQ / Redis
- Celery only if needed
- simple cron + worker loop acceptable for first pass

### Local AI
- Ollama, vLLM, or equivalent local inference runner
- small/medium local LLM for extraction and reasoning
- local vision model for image scoring if available
- prompt templates under version control

### Frontend
- Next.js internal dashboard
- or a minimal React app
- or even FastAPI templates for earliest scaffold if speed matters

---

## Data Model

## Core Tables

### `sources`
Configuration per auction source.

Fields:
- id
- name
- base_url
- enabled
- fetch_strategy
- parser_name
- rate_limit_policy
- buyer_premium_policy
- created_at
- updated_at

### `lots`
Canonical lot record.

Fields:
- id
- source_id
- external_lot_id
- lot_url
- canonical_title
- status
- first_seen_at
- last_seen_at
- last_fetched_at
- created_at
- updated_at

Status examples:
- active
- ended
- sold
- withdrawn
- archived

### `lot_fetches`
One record per fetch event.

Fields:
- id
- lot_id
- fetched_at
- fetch_type
- http_status
- content_hash
- raw_html_path
- raw_text_path
- screenshot_path nullable
- parser_version
- success
- error_message nullable

### `lot_images`
Fields:
- id
- lot_id
- image_url
- local_path nullable
- sort_order
- fetched_at

### `parsed_lot_fields`
Structured parse output, versioned.

Fields:
- id
- lot_id
- lot_fetch_id
- parser_version
- title
- subtitle
- description
- category_raw
- condition_text
- dimensions_text
- current_bid
- estimate_low
- estimate_high
- currency
- auction_end_time
- time_left_text
- provenance_text
- seller_location
- auction_house_name
- raw_designer_mentions jsonb
- raw_material_mentions jsonb
- parse_confidence
- created_at

### `normalized_lot_fields`
Canonicalized fields, versioned.

Fields:
- id
- lot_id
- parsed_lot_fields_id
- normalizer_version
- designer_entity_id nullable
- producer_entity_id nullable
- object_type_id nullable
- era_label nullable
- materials jsonb
- normalized_category
- normalization_confidence
- created_at

### `entities`
Known people / brands / producers / styles.

Fields:
- id
- entity_type
- canonical_name
- aliases jsonb
- country nullable
- active_years nullable
- notes nullable

Entity types:
- designer
- producer
- brand
- manufacturer
- style
- workshop

### `comparables`
Historical comp records.

Fields:
- id
- entity_id nullable
- source_name
- external_ref nullable
- title
- object_type
- material_tags jsonb
- sold_price
- currency
- sold_at
- country nullable
- confidence
- raw_payload jsonb

### `enrichment_runs`
Track each agent run.

Fields:
- id
- lot_id
- agent_name
- agent_version
- model_name
- prompt_version
- input_hash
- started_at
- completed_at
- success
- error_message nullable

### `enrichment_outputs`
Structured output of each agent.

Fields:
- id
- enrichment_run_id
- lot_id
- output_json jsonb
- score_primary nullable
- confidence nullable
- created_at

### `lot_scores`
Resolved latest scores for easy querying.

Fields:
- id
- lot_id
- scoring_version
- arbitrage_score nullable
- norway_gap_score nullable
- taste_score nullable
- wildcard_score nullable
- urgency_score nullable
- overall_watch_score nullable
- explanation_json jsonb
- created_at
- updated_at

### `user_actions`
Fields:
- id
- lot_id
- action_type
- note nullable
- created_at

Action types:
- star
- skip
- watch
- archive
- bought
- false_positive
- note

---

## Parsing Strategy

### General Rules

1. Do not rely on AI for obvious numeric fields.
2. Parse source-specific fields using deterministic selectors first.
3. Store raw text blocks in addition to parsed fields.
4. Preserve source wording for condition and provenance.
5. Keep parser versions explicit.

### Parsing Pipeline

1. Fetch page
2. Save raw HTML
3. Extract text blocks and candidate structured fields
4. Normalize numeric formats and currencies
5. Save parsed record
6. Trigger normalization + enrichment jobs

---

## Agent Design

### Important Constraint

Do not build “freeform autonomous agents” first.

Implement **bounded job-based agents**:
- one input schema
- one output schema
- one clear task
- one explicit retry policy

### General Agent Rules

- output must be valid JSON
- include confidence
- include risk flags
- include short rationale
- avoid hallucinated certainty
- prefer `null` over guessing when confidence is low

### Failure Behavior

If an agent fails:
- mark run failed
- keep lot available in UI with partial data
- retry later if appropriate
- do not overwrite prior successful output unless explicitly intended

---

## Scoring

## 1. Arbitrage Score

Purpose:
- estimate whether this lot is attractive from a value perspective

Candidate formula:
```text
arbitrage_score =
0.40 * price_gap_score +
0.20 * norway_premium_score +
0.15 * attribution_confidence_score +
0.10 * condition_score +
0.10 * liquidity_score +
0.05 * timing_score
```

### Inputs
- expected fair value vs current bid
- expected Norway premium
- attribution confidence
- condition/risk
- category liquidity
- urgency

## 2. Taste Score

Purpose:
- estimate whether this is aligned with known or adjacent taste

Candidate formula:
```text
taste_score =
0.35 * designer_similarity +
0.20 * visual_similarity +
0.15 * material_fit +
0.15 * era_fit +
0.10 * user_behavior_match +
0.05 * novelty_bonus
```

## 3. Wild-Card Score

Purpose:
- estimate whether the object is unusually visually compelling

Candidate formula:
```text
wildcard_score =
0.35 * image_distinctiveness +
0.20 * sculptural_presence +
0.15 * rarity_cues +
0.10 * material_luxury +
0.10 * provenance_interest +
0.10 * manual_curator_boost
```

### Rule
For MVP, keep the three scores separate in the interface.

---

## Norway Arbitrage Logic

This is a key wedge and should be first-class.

For lots sourced in Sweden, estimate:

```text
norway_gap =
expected_norway_value - landed_acquisition_cost
```

Where landed acquisition cost may include:
- current bid or projected hammer
- buyer's premium
- VAT if applicable
- transport / logistics estimate
- restoration buffer
- import-related cost assumptions if relevant

Store both:
- raw monetary gap
- normalized Norway gap score

Possible labels:
- Strong Norway Arbitrage
- Moderate Norway Arbitrage
- Weak Edge
- No Edge

---

## Comparable Data Strategy

The comp engine should be mostly deterministic.

### Minimum viable comparables
Use:
- same designer + same object type
- same designer + similar materials
- same producer / brand + similar object type
- same category + era if attribution weak

### Comparison outputs
Return:
- comp count
- median sold price
- low/high band
- quality/confidence
- market geography hints

### Important Rule
AI may interpret comps, but should not replace the comp store itself.

---

## Dashboard Requirements

## Main Views

### Best Buys
Show lots with strongest arbitrage score and sufficient confidence.

### Norway Arbitrage
Show lots with strongest Sweden-to-Norway resale gap.

### Your Taste
Show high taste-score lots including adjacent designers.

### Wild Cards
Show high wildcard-score visually exceptional lots.

### Ending Soon
Show lots that are ending soon and above configurable thresholds.

### Watchlist
Show all manually watched lots with latest refresh state.

## Lot Card Must Show
- image
- title
- source
- current bid
- estimate
- end time / time remaining
- top labels
- top score(s)
- short rationale
- key risk flags
- actions: star / skip / watch / archive / note

## Lot Detail Must Show
- source link
- source metadata
- parsed fields
- normalized fields
- agent outputs
- latest scores
- fetch history
- raw snapshot references
- notes and user actions

---

## API Endpoints (Suggested)

### Ingestion / Jobs
- `POST /jobs/fetch/source/{source_name}`
- `POST /jobs/fetch/lot/{lot_id}`
- `POST /jobs/parse/{lot_fetch_id}`
- `POST /jobs/enrich/{lot_id}`
- `POST /jobs/rescore/{lot_id}`

### Lots
- `GET /lots`
- `GET /lots/{id}`
- `GET /lots/{id}/history`
- `GET /lots/{id}/scores`
- `GET /lots/{id}/enrichments`

### Views
- `GET /views/best-buys`
- `GET /views/norway-arbitrage`
- `GET /views/taste`
- `GET /views/wildcards`
- `GET /views/ending-soon`
- `GET /views/watchlist`

### Actions
- `POST /lots/{id}/star`
- `POST /lots/{id}/skip`
- `POST /lots/{id}/watch`
- `POST /lots/{id}/archive`
- `POST /lots/{id}/note`

---

## Scheduler Behavior

Suggested jobs:

### Broad Source Crawl
- enumerate active listings
- upsert unseen lots
- refresh active tracked lots
- cadence: 30–120 min

### Watchlist Refresh
- refresh watched lots
- cadence based on time-to-end

### Enrichment Queue
- trigger on:
  - new lot
  - changed content hash
  - manual rerun
  - model/prompt version bump

### End-State Sync
- detect ended/sold/withdrawn lots
- finalize status
- record final visible bid if available

---

## Configuration

Use config files or env vars for:

- source enable/disable
- rate limits
- refresh cadences
- watched-lot cadence thresholds
- fee assumptions
- shipping/restoration assumptions
- model names
- prompt versions
- scoring weights
- seed designers
- seed materials
- preferred object categories

Suggested checked-in config:
- `config/designers.yaml`
- `config/categories.yaml`
- `config/materials.yaml`
- `config/scoring.yaml`
- `config/sources.yaml`

---

## Seed Designer List (Initial)

Include an editable config list such as:

- Hans Wegner
- Finn Juhl
- Arne Jacobsen
- Eero Saarinen
- Bruno Mathsson
- Ingmar Relling
- Børge Mogensen
- Poul Kjærholm
- Verner Panton
- Niels Otto Møller
- Ole Wanscher
- Ib Kofod-Larsen
- Illum Wikkelsø
- Kai Kristiansen

This list should be easy to modify.

---

## Prompt / Output Contracts

Prompt templates must be versioned.

Suggested folder:
```text
docs/prompts/
  attribution_v1.md
  arbitrage_v1.md
  taste_v1.md
  wildcard_v1.md
```

Each prompt spec should define:
- purpose
- input schema
- output schema
- confidence expectations
- failure conventions

All agent outputs should validate against Pydantic models.

---

## Logging and Observability

Must log:
- fetch success/failure
- parse success/failure
- changed content hash
- agent run start/finish
- output validation failure
- score generation failure
- retry counts

Useful metrics:
- lots fetched per source
- parse success rate
- agent success rate
- avg enrichment latency
- lots refreshed in last N hours
- number of ending-soon high-priority lots
- number of starred lots
- false-positive count

---

## Security / Compliance Notes

Implementation agent should:
- respect source rate limits
- implement conservative fetch cadence
- isolate source-specific logic
- make fetch policies configurable
- avoid aggressive parallelism by default

This repo should not implement automated bidding.

---

## MVP Milestones

## Milestone 1 — Skeleton
- repo scaffold
- DB setup
- migrations
- basic FastAPI app
- basic worker
- source config
- health checks

## Milestone 2 — Ingestion
- fetch Auctionet listings + detail pages
- fetch Bukowskis listings + detail pages
- store raw HTML per fetch
- save parsed fields

## Milestone 3 — Normalization
- canonical entity handling
- object/material/era normalization
- currency normalization

## Milestone 4 — Enrichment
- attribution agent
- arbitrage agent
- taste agent
- placeholder wildcard agent

## Milestone 5 — Ranking + UI
- main ranked views
- lot detail page
- watch/star/skip actions

## Milestone 6 — Monitoring
- scheduled refresh
- ending-soon priority logic
- rerun enrichment on content changes

---

## First Tasks for the Implementation Agent

1. Initialize repo structure.
2. Create PostgreSQL schema and migrations for core tables.
3. Implement source config system.
4. Implement fetch pipeline with raw HTML snapshot storage.
5. Implement parser interface and source-specific parsers.
6. Build parsed-field persistence layer.
7. Add normalization layer and canonical entity models.
8. Add enrichment job framework with strict JSON outputs.
9. Add a first attribution agent contract.
10. Build simple internal UI with Best Buys and Watchlist views.
11. Add user actions and reranking hooks.
12. Add seed designer config and scoring config.

---

## Acceptance Criteria for MVP

The MVP is acceptable when:

- new lots can be ingested from Auctionet and Bukowskis
- each fetch creates a raw HTML snapshot record
- deterministic parsing extracts core auction fields
- a lot can be enriched locally with structured outputs
- ranked views are queryable and visible in a dashboard
- users can star, skip, and watch lots
- watched lots refresh on tighter cadences near end time
- each surfaced lot shows reasons and risk flags
- enrichment and scoring can be rerun without refetching source pages

---

## Open Questions for Later Iterations

- best local model stack for text and vision
- whether to store local image binaries or URLs only
- how to source and refresh comp data at scale
- whether to add OCR fallback for images with text overlays
- whether to add vector similarity for visual discovery
- whether to model buyer's premium dynamically per source/auction
- whether to introduce dealer-export workflows later

---

## Final Summary

Build a local-AI-assisted sourcing engine for auction lots.

The MVP should:
- collect listings from Auctionet and Bukowskis
- store raw HTML snapshots per fetch run
- parse and normalize lot data
- enrich each lot using bounded local AI jobs
- rank opportunities across arbitrage, taste adjacency, and visual distinctiveness
- support a simple watchlist-driven internal dashboard

The implementation should emphasize:
- auditability
- rerunnability
- structured outputs
- modular source parsers
- modular agent jobs
- human-guided buying decisions
