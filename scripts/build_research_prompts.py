#!/usr/bin/env python3
"""Build research prompts for all lots using enrichment data."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

ENRICHMENTS_DIR = Path("data/enrichments")
OUTPUT_FILE = Path("data/research_prompts.json")


def build_prompt(lot_id: str, enrichment: dict) -> str:
    """Build a research prompt from enrichment data."""
    title = enrichment.get("title", "Unknown")
    designer = enrichment.get("designer", {})
    manufacturer = enrichment.get("manufacturer", {})
    model = enrichment.get("model", {})
    materials = enrichment.get("materials", [])
    auction = enrichment.get("auction", {})
    categories = enrichment.get("categories", [])
    era = enrichment.get("era", "")
    object_type = enrichment.get("object_type", "furniture")

    designer_name = designer.get("name") if isinstance(designer, dict) else None
    mfr_name = manufacturer.get("name") if isinstance(manufacturer, dict) else None
    model_name = model.get("name_or_number") or model.get("name") if isinstance(model, dict) else None
    estimate = auction.get("estimate_eur")
    location = auction.get("location", "")
    house = auction.get("house", "")

    # Build search terms
    search_terms = []
    if designer_name:
        search_terms.append(designer_name)
    if model_name:
        search_terms.append(str(model_name))
    if mfr_name and mfr_name != designer_name:
        search_terms.append(mfr_name)

    # Material list
    mat_list = []
    for m in materials:
        if isinstance(m, str):
            mat_list.append(m)
        elif isinstance(m, dict):
            mat_list.append(m.get("material", ""))

    search_query = " ".join(search_terms) if search_terms else title

    prompt = f"""You are a furniture market research agent. Find REAL current prices for this auction lot.

THE LOT:
- Title: {title}
- Designer: {designer_name or 'Unknown'}
- Manufacturer: {mfr_name or 'Unknown'}
- Model: {model_name or 'Unknown'}
- Materials: {', '.join(mat_list) if mat_list else 'Not specified'}
- Era: {era}
- Object type: {object_type}
- Auction estimate: {estimate} EUR
- Location: {location}
- Auction house: {house}

SEARCH STRATEGY:
1. Search for "{search_query}" on dealer platforms (1stDibs, Pamono)
2. Search for "{search_query} auction results" on Barnebys, Lauritz, or past Auctionet results
3. CRITICAL — Norwegian market prices: Search Blomqvist auction results at blomqvist.no/auksjoner/solgte-objekter?search={search_query} for Norwegian hammer prices (tilslag). This is the target resale market.
4. Search FINN.no for current Norwegian asking prices: finn.no/bap/forsale/search.html?q={search_query}
5. If designer is known, search for their work on Nordiska Galleriet (nordiskagalleriet.no) for Norwegian retail prices
6. If manufacturer is known, check their website for current retail prices

For UNKNOWN/UNATTRIBUTED pieces, search more broadly:
- "{object_type} {', '.join(mat_list[:2]) if mat_list else ''} {era} auction"
- Focus on comparable style/era/material rather than exact match

Return JSON:
{{
  "lot_id": "{lot_id}",
  "search_terms_used": ["..."],
  "comparables": [
    {{
      "source": "url",
      "platform": "name",
      "description": "...",
      "price": 0,
      "currency": "EUR/USD/SEK/NOK/DKK/GBP",
      "condition": "new/vintage/restored/fair",
      "date": "YYYY-MM",
      "relevance": "high/medium/low"
    }}
  ],
  "retail_new_price": {{"price": null, "currency": "EUR", "source": "url or null"}},
  "dealer_price_range": {{"low": null, "high": null, "currency": "EUR"}},
  "auction_price_range": {{"low": null, "high": null, "currency": "EUR"}},
  "norway_retail_price": {{"price": null, "currency": "NOK", "source": "url or null"}},
  "grounded_estimate": {{
    "low": null,
    "high": null,
    "currency": "EUR",
    "basis": "Explain which comparables support this estimate"
  }},
  "comparable_search_terms": ["term1", "term2"],
  "research_confidence": 0.0-1.0,
  "research_notes": "Any caveats, e.g. 'no exact comparables found, estimate based on similar pieces'"
}}

IMPORTANT — comparable_search_terms:
In addition to your research, output a "comparable_search_terms" array with 3-8 short search
phrases that would find SIMILAR items in a furniture pricing database. These terms will be used
for automated matching, so be specific:
- Include model names/numbers (e.g. "J39", "model 2212", "Trinidad 3297", "FM shelf")
- Include designer + object type combos (e.g. "Mogensen armchair", "Wegner dining chair")
- Include manufacturer + material combos (e.g. "Fredericia teak", "Bramin rosewood")
- For unattributed pieces, use descriptive terms (e.g. "Danish teak sideboard 1960s", "oak dining set")
- Include Norwegian/Scandinavian retail search terms (e.g. "teak spisebord", "dansk lenestol")

Use WebSearch and WebFetch to find real data. Aim for 3-10 comparables. If you can't find exact matches, find the closest comparable pieces and note the differences."""

    return prompt


def main():
    lot_ids = json.loads(Path("data/lot_ids.json").read_text())
    prompts = {}
    skipped = 0

    for lid in lot_ids:
        enrichment_file = ENRICHMENTS_DIR / f"{lid}.json"
        if not enrichment_file.exists():
            skipped += 1
            continue

        data = json.loads(enrichment_file.read_text())
        prompt = build_prompt(lid, data)
        prompts[lid] = prompt

    OUTPUT_FILE.write_text(json.dumps(prompts, indent=2))
    print(f"Built {len(prompts)} research prompts, skipped {skipped}")
    print(f"Saved to {OUTPUT_FILE}")

    # Print a sample
    sample_id = list(prompts.keys())[0]
    print(f"\n--- Sample prompt for lot {sample_id} ---")
    print(prompts[sample_id][:500] + "...")


if __name__ == "__main__":
    main()
