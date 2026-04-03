"""Pre-filter scoring: score lots from URL slug before expensive detail fetch.

Scores each lot 0-6 based on title keywords extracted from the Auctionet URL slug.
Designed to run on listing page data only (no detail page fetch needed).

Tiers:
  score >= 3  →  Auto-fetch + enrich (designer + material signal)
  score 0-2   →  Fetch detail, but gate enrichment behind Haiku triage
  score < 0   →  Skip entirely (anti-signals dominate)
"""

import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# --- Tier 1: Designer/maker names (+3) ---
# These names in a URL slug strongly predict strong_buy/undervalued (69% hit rate).
TIER1_DESIGNERS = {
    # Danish golden age
    "mogensen", "wegner", "jacobsen", "juhl", "kjaerholm", "kjaernulf",
    "kjærnulf", "ditzel", "vodder", "kristiansen", "wanscher", "moller",
    "møller", "henningsen", "andersen", "buch", "jalk", "wikkelso",
    "wikkelsø", "olsen",
    # Swedish
    "malmsten", "mathsson", "ekstrom", "ekström", "svensson", "skogh",
    "fridhagen", "malmvall", "larsson", "feuk", "ekselius", "ressell",
    "hilland", "blomstedt", "holmquist",
    # Norwegian
    "afdal", "relling", "ressell", "ertzeid", "rykken",
    # International icons
    "eames", "bertoia", "knoll", "breuer", "aalto", "saarinen",
    "panton", "hoffmann", "le-corbusier", "lissoni", "meda",
    "ducaroy", "tusquets", "tapiovaara", "haussmann", "pontoppidan",
    "nyrop",
    # Manufacturers
    "fritz-hansen", "getama", "bramin", "de-sede", "cassina", "vitra",
    "thonet", "dux", "stolab", "ligne-roset", "knoll", "zanotta",
    "swedese", "wittmann", "rud-rasmussen", "boije", "moooi",
    "fredericia",
}

# --- Tier 2: Material/origin signals (+2) ---
TIER2_SIGNALS = {
    "rosewood", "teak", "walnut", "jacaranda", "oak",
    "leather", "cognac",
    "danish", "denmark", "scandinavian",
    "mid-century", "1950s", "1960s", "1970s",
    "model", "series", "designed",
}

# --- Tier 3: High-value object types (+1) ---
TIER3_TYPES = {
    "sofa", "three-seater", "two-seater", "daybed",
    "armchairs", "armchair", "lounge-chair",
    "dining-chairs",
    "sideboard", "credenza", "highboard", "tallboy",
    "secretary", "bureau", "secretaire",
    "nesting-tables", "coffee-table",
    "cabinet", "bookcase",
}

# --- Anti-signals (-2) ---
SKIP_SIGNALS = {
    "contemporary", "rococo", "reproduction", "replica",
    "garden", "patio", "outdoor",
    "ikea", "mio",
    "edwardian", "victorian",
    "bar-stool", "bar-stools",
    "office-chair", "conference",
    "childr", "highchair",
    "pine-chairs",
}


def slug_from_url(lot_url: str) -> str:
    """Extract the title slug from an Auctionet URL.

    /en/4949145-borge-mogensen-chair-leather → 'borge mogensen chair leather'
    """
    match = re.search(r"/en/\d+-(.+?)(?:\?|$)", lot_url)
    if not match:
        return ""
    return match.group(1).replace("-", " ").lower()


def score_slug(slug: str) -> tuple[int, list[str]]:
    """Score a URL slug. Returns (score, list of matched signals)."""
    score = 0
    signals = []

    # Check words individually and as bigrams
    words = set(slug.split())
    # Also check the full slug for multi-word matches
    text = slug

    for designer in TIER1_DESIGNERS:
        # Handle multi-word designers (e.g. "fritz-hansen" → "fritz hansen")
        if designer.replace("-", " ") in text:
            score += 3
            signals.append(f"+3 designer:{designer}")
            break  # Only count one designer match

    for signal in TIER2_SIGNALS:
        if signal.replace("-", " ") in text:
            score += 2
            signals.append(f"+2 material:{signal}")
            break  # Only count one material match

    for obj_type in TIER3_TYPES:
        if obj_type.replace("-", " ") in text:
            score += 1
            signals.append(f"+1 type:{obj_type}")
            break  # Only count one type match

    for skip in SKIP_SIGNALS:
        if skip.replace("-", " ") in text:
            score -= 2
            signals.append(f"-2 skip:{skip}")
            break  # Only count one skip match

    return score, signals


def score_lot_url(lot_url: str) -> tuple[int, str, list[str]]:
    """Score a lot from its URL alone.

    Returns: (score, slug_text, matched_signals)
    """
    slug = slug_from_url(lot_url)
    score, signals = score_slug(slug)
    return score, slug, signals


def classify_lot(score: int) -> str:
    """Classify lot into a tier based on pre-filter score.

    Returns: 'auto' | 'gate' | 'skip'
    """
    if score >= 3:
        return "auto"   # Straight to detail fetch + enrichment
    elif score >= 0:
        return "gate"   # Fetch detail, but gate enrichment behind Haiku
    else:
        return "skip"   # Don't even fetch the detail page


def filter_listing_lots(
    lot_list: list[dict],
    min_score: int = 0,
    existing_ids: set[str] | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Score and partition a listing page of lots into tiers.

    Args:
        lot_list: List of {external_lot_id, lot_url} from fetch_listing_page
        min_score: Minimum score to fetch (default 0 = skip only anti-signal lots)
        existing_ids: Set of external_lot_ids already in DB (skip these)

    Returns:
        (auto_lots, gate_lots, skip_lots)
    """
    existing_ids = existing_ids or set()
    auto_lots = []
    gate_lots = []
    skip_lots = []

    for lot in lot_list:
        ext_id = lot["external_lot_id"]
        if ext_id in existing_ids:
            continue

        score, slug, signals = score_lot_url(lot["lot_url"])
        lot["prefilter_score"] = score
        lot["prefilter_slug"] = slug
        lot["prefilter_signals"] = signals

        tier = classify_lot(score)
        if tier == "auto":
            auto_lots.append(lot)
        elif tier == "gate":
            gate_lots.append(lot)
        else:
            skip_lots.append(lot)

    return auto_lots, gate_lots, skip_lots
