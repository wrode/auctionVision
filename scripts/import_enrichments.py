#!/usr/bin/env python3
"""Import enrichment JSONs into the database and compute scores."""
import json
import sys
import logging
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

import yaml

ENRICHMENTS_DIR = Path("data/enrichments")

# Load resale costs config for landed cost calculation
_resale_config_path = Path(__file__).parent.parent / "config" / "resale_costs.yaml"
_resale_config = yaml.safe_load(_resale_config_path.read_text()) if _resale_config_path.exists() else {}
_resale = _resale_config.get("resale_arbitrage", {})
BUYER_PREMIUM_RATE = _resale.get("buyer_premium_rate", 0.20)
VAT_ON_PREMIUM_RATE = _resale.get("vat_on_premium_rate", 0.25)
TRANSPORT_BASE = _resale.get("transport", {})
TRANSPORT_LOCATION_MULTIPLIER = _resale.get("transport_location_multiplier", {})

SEK_TO_EUR = 0.087


def _get_location_multiplier(seller_location, multiplier_map):
    """Look up transport multiplier for a seller location."""
    if not seller_location or not multiplier_map:
        return multiplier_map.get("_default_unknown", 1.5)
    if seller_location in multiplier_map:
        return multiplier_map[seller_location]
    parts = seller_location.rsplit(", ", 1)
    if len(parts) == 2:
        country_key = f"_default_{parts[1].strip()}"
        if country_key in multiplier_map:
            return multiplier_map[country_key]
    return multiplier_map.get("_default_unknown", 1.5)


def compute_landed_cost(estimate_eur, object_type=None, seller_location=None, current_bid=None):
    """Compute landed cost: assumed_hammer + premium + VAT on premium + location-based transport.

    Uses current_bid as hammer estimate, or estimate/2 if no bid.
    """
    if not estimate_eur or estimate_eur <= 0:
        return None

    hammer = current_bid if current_bid and current_bid > 0 else estimate_eur / 2
    premium = hammer * BUYER_PREMIUM_RATE
    vat_on_premium = premium * VAT_ON_PREMIUM_RATE

    # Transport by object type
    transport_sek = TRANSPORT_BASE.get("medium_item", 3000)
    if object_type:
        t = object_type.lower()
        if any(w in t for w in ["sofa", "large", "sectional", "dining set", "bed"]):
            transport_sek = TRANSPORT_BASE.get("oversized_item", 8000)
        elif any(w in t for w in ["table", "sideboard", "cabinet", "shelving", "chest", "bookcase", "wardrobe"]):
            transport_sek = TRANSPORT_BASE.get("large_item", 5000)
        elif any(w in t for w in ["lamp", "stool", "small", "mirror", "cover"]):
            transport_sek = TRANSPORT_BASE.get("small_item", 1500)

    # Location multiplier
    loc_mult = _get_location_multiplier(seller_location, TRANSPORT_LOCATION_MULTIPLIER)
    transport_eur = (transport_sek * loc_mult) * SEK_TO_EUR

    return round(hammer + premium + vat_on_premium + transport_eur)


# Map condition_grade text to a numeric score
CONDITION_SCORES = {
    "excellent": 1.0, "very_good": 0.85, "good": 0.7,
    "fair": 0.5, "poor": 0.25, "unknown": 0.4,
}


def score_from_enrichment(data: dict, end_time_str: str = None) -> dict:
    """Derive numeric scores from enrichment JSON."""
    designer = data.get("designer", {})
    enrichment = data.get("enrichment", {})
    condition = data.get("condition_grade", "fair")

    # Normalize condition grade
    if isinstance(condition, str):
        condition = condition.lower().replace("+", "").replace("-", "").replace("b", "good").replace("c", "fair").strip()
    cond_score = CONDITION_SCORES.get(condition, 0.4)

    # Designer confidence
    conf = designer.get("confidence", 0) if isinstance(designer.get("confidence"), (int, float)) else 0
    attr_type = designer.get("attribution_type", "unknown")
    if attr_type == "confirmed":
        conf = max(conf, 0.85)

    # Collectibility keyword scoring
    collect_text = str(enrichment.get("collectibility", "")).lower()
    collect_score = 0.3
    if any(w in collect_text for w in ["very high", "extremely high", "museum", "iconic"]):
        collect_score = 0.95
    elif any(w in collect_text for w in ["high", "blue-chip", "strong"]):
        collect_score = 0.75
    elif any(w in collect_text for w in ["moderate", "medium", "rising"]):
        collect_score = 0.5
    elif any(w in collect_text for w in ["low", "none", "very low", "minimal"]):
        collect_score = 0.15

    # Opportunity scoring: prefer actual resale multiplier, fall back to keywords
    resale_eur = data.get("estimated_resale_eur", {})
    resale_mid = None
    if isinstance(resale_eur, dict) and resale_eur.get("low") and resale_eur.get("high"):
        resale_mid = (resale_eur["low"] + resale_eur["high"]) / 2

    # Get acquisition cost (estimate + 20% buyer premium)
    estimate = None
    auction = data.get("auction", {})
    if auction.get("estimate_eur"):
        estimate = auction["estimate_eur"]
    elif data.get("estimate_low"):
        estimate = data["estimate_low"]

    if resale_mid and estimate and estimate > 0:
        acquisition = estimate * 1.20  # 20% buyer premium
        multiplier = resale_mid / acquisition
        # Map multiplier to score: <1.5x = 0.1, 2x = 0.5, 3x = 0.8, 4x+ = 1.0
        if multiplier >= 4.0:
            opp_score = 1.0
        elif multiplier >= 3.0:
            opp_score = 0.8 + 0.2 * (multiplier - 3.0)
        elif multiplier >= 2.0:
            opp_score = 0.5 + 0.3 * (multiplier - 2.0)
        elif multiplier >= 1.5:
            opp_score = 0.2 + 0.3 * (multiplier - 1.5) / 0.5
        else:
            opp_score = max(0.05, multiplier / 10)
    elif resale_mid and not estimate:
        # No estimate = unknown acquisition cost. Use opportunity_notes keywords.
        opp_text = str(data.get("opportunity_notes", "")).lower()
        if any(w in opp_text for w in ["strong_buy", "strong buy"]):
            opp_score = 0.90
        elif any(w in opp_text for w in ["undervalued"]):
            opp_score = 0.70
        else:
            opp_score = 0.50
    else:
        # Fall back to keyword matching
        opp_text = str(data.get("opportunity_notes", enrichment.get("opportunity_notes", ""))).lower()
        opp_score = 0.3
        if any(w in opp_text for w in ["strong_buy", "strong buy", "significantly undervalued"]):
            opp_score = 0.95
        elif any(w in opp_text for w in ["undervalued", "strong value", "good value"]):
            opp_score = 0.75
        elif any(w in opp_text for w in ["reasonable", "fair_value", "fair value", "modest"]):
            opp_score = 0.45
        elif any(w in opp_text for w in ["skip", "overpriced", "limited", "not recommended", "pass"]):
            opp_score = 0.1

    # Compose scores
    arbitrage_score = round(opp_score * 0.6 + cond_score * 0.2 + conf * 0.2, 3)
    taste_score = round(collect_score * 0.5 + conf * 0.3 + cond_score * 0.2, 3)
    wildcard_score = round(collect_score * 0.4 + opp_score * 0.4 + cond_score * 0.2, 3)

    # Urgency from auction end time
    urgency = None
    auction = data.get("auction", {})
    end_time = auction.get("end_time") or auction.get("end_date") or auction.get("ends")
    if end_time and isinstance(end_time, str):
        try:
            # Try ISO format
            from dateutil import parser as dtparser
            dt = dtparser.parse(end_time)
            now = datetime.now(timezone.utc)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            hours_left = (dt - now).total_seconds() / 3600
            if hours_left < 0:
                urgency = 0.0
            elif hours_left < 1:
                urgency = 1.0
            elif hours_left < 6:
                urgency = max(0.5, 1.0 - (hours_left - 1) / 10)
            else:
                urgency = max(0.0, 1.0 - hours_left / 24)
        except Exception:
            urgency = None

    # Overall
    components = [s for s in [arbitrage_score, taste_score, wildcard_score] if s is not None]
    overall = round(sum(components) / len(components), 3) if components else None

    return {
        "arbitrage_score": arbitrage_score,
        "resale_arb_score": arbitrage_score,
        "taste_score": taste_score,
        "wildcard_score": wildcard_score,
        "urgency_score": urgency,
        "overall_watch_score": overall,
    }


def run():
    from backend.database import SessionLocal, init_db
    from backend.models import Lot, EnrichmentRun, EnrichmentOutput, LotScores, ParsedLotFields

    init_db()
    db = SessionLocal()

    # Load all enrichment JSONs
    enrichment_files = sorted(ENRICHMENTS_DIR.glob("*.json"))
    enrichment_files = [f for f in enrichment_files if not f.name.startswith("_")]

    # Build external_lot_id -> db lot_id mapping
    lots = db.query(Lot).all()
    ext_to_lot = {lot.external_lot_id: lot for lot in lots}

    imported = 0
    scored = 0

    for f in enrichment_files:
        ext_id = f.stem  # filename is {external_lot_id}.json
        lot = ext_to_lot.get(ext_id)
        if not lot:
            logger.warning(f"No lot found for external_id {ext_id}, skipping")
            continue

        data = json.loads(f.read_text())

        # Import enrichment
        run_record = EnrichmentRun(
            lot_id=lot.id,
            agent_name="lot_enrichment",
            agent_version="claude_opus_v1",
            model_name="claude-opus-4-6",
            success=1,
        )
        db.add(run_record)
        db.flush()

        output = EnrichmentOutput(
            enrichment_run_id=run_record.id,
            lot_id=lot.id,
            output_json=data,
            confidence=float(data["designer"]["confidence"]) if isinstance(data.get("designer", {}).get("confidence"), (int, float)) else None,
        )
        db.add(output)

        # Update lot canonical title from enrichment
        if data.get("title") and not lot.canonical_title:
            lot.canonical_title = data["title"]

        # Also create a basic ParsedLotFields if none exists
        existing_parsed = db.query(ParsedLotFields).filter(ParsedLotFields.lot_id == lot.id).order_by(ParsedLotFields.id.desc()).first()
        auction = data.get("auction", {})
        dims = data.get("dimensions", {})

        # Parse auction end time
        end_time_val = None
        end_time_raw = auction.get("end_time") or auction.get("end_date") or auction.get("ends")
        if end_time_raw and isinstance(end_time_raw, str):
            try:
                from dateutil import parser as dtparser
                end_time_val = dtparser.parse(end_time_raw)
            except Exception:
                pass

        # Build dimensions text
        dims_parts = []
        if dims.get("height_cm"):
            dims_parts.append(f"H {dims['height_cm']} cm")
        if dims.get("width_cm"):
            dims_parts.append(f"W {dims['width_cm']} cm")
        if dims.get("depth_cm"):
            dims_parts.append(f"D {dims['depth_cm']} cm")
        dims_text = ", ".join(dims_parts) if dims_parts else None

        if not existing_parsed:
            plf = ParsedLotFields(
                lot_id=lot.id,
                lot_fetch_id=lot.fetches[0].id if lot.fetches else None,
                parser_version="enrichment_v1",
                title=data.get("title"),
                description=data.get("condition_summary"),
                category_raw=", ".join(data.get("categories", [])),
                condition_text=data.get("condition_summary"),
                dimensions_text=dims_text,
                current_bid=auction.get("current_bid_eur"),
                estimate_low=auction.get("estimate_eur"),
                estimate_high=auction.get("estimate_eur"),
                currency="EUR",
                auction_end_time=end_time_val,
                seller_location=auction.get("location"),
                auction_house_name=auction.get("house"),
                raw_designer_mentions=json.dumps(
                    [data["designer"]["name"]] if data.get("designer", {}).get("name") else []
                ),
                raw_material_mentions=json.dumps(
                    [m if isinstance(m, str) else m.get("material", "") for m in data.get("materials", [])]
                ),
                parse_confidence=0.9,
            )
            db.add(plf)
        else:
            # Update existing record with missing fields
            if not existing_parsed.auction_end_time and end_time_val:
                existing_parsed.auction_end_time = end_time_val
            if not existing_parsed.dimensions_text and dims_text:
                existing_parsed.dimensions_text = dims_text
            if not existing_parsed.current_bid and auction.get("current_bid_eur"):
                existing_parsed.current_bid = auction.get("current_bid_eur")

        imported += 1

        # Compute scores
        scores_data = score_from_enrichment(data)
        lot_scores = db.query(LotScores).filter(LotScores.lot_id == lot.id).first()
        if not lot_scores:
            lot_scores = LotScores(lot_id=lot.id)
        lot_scores.scoring_version = "enrichment_v1"
        lot_scores.arbitrage_score = scores_data["arbitrage_score"]
        lot_scores.resale_arb_score = scores_data["resale_arb_score"]
        lot_scores.taste_score = scores_data["taste_score"]
        lot_scores.wildcard_score = scores_data["wildcard_score"]
        lot_scores.urgency_score = scores_data["urgency_score"]
        lot_scores.overall_watch_score = scores_data["overall_watch_score"]

        # Build explanation with resale estimates for the frontend
        # Support both v1 (flat) and v2 (nested) enrichment formats
        valuation = data.get("valuation", {})
        resale = valuation.get("estimated_resale_eur") or data.get("estimated_resale_eur", {})
        expl = dict(scores_data)

        if isinstance(resale, dict) and resale.get("low"):
            expl["ai_value_low"] = resale["low"]
            expl["ai_value_high"] = resale["high"]
            expl["ai_value_basis"] = data.get("reasoning", "")
            expl["estimate_basis"] = valuation.get("estimate_basis") or data.get("estimate_basis")
            expl["estimate_confidence"] = valuation.get("estimate_confidence") or data.get("estimate_confidence")
            expl["conviction"] = valuation.get("conviction") or data.get("conviction")
            expl["best_market"] = valuation.get("best_market") or data.get("best_market")
            expl["best_market_reasoning"] = valuation.get("best_market_reasoning") or data.get("best_market_reasoning")

        # v2 fields
        expl["enrichment_version"] = data.get("enrichment_version")
        if data.get("buyer_profile"):
            expl["buyer_profile"] = data["buyer_profile"]
        if data.get("listing"):
            expl["listing"] = data["listing"]
        if data.get("inspection_checklist"):
            expl["inspection_checklist"] = data["inspection_checklist"]

        # Compute landed cost using seller location + object type
        seller_loc = None
        object_type = None
        parsed_record = existing_parsed or locals().get('plf')
        if parsed_record:
            seller_loc = parsed_record.seller_location
        if not seller_loc:
            seller_loc = auction.get("location")

        # Get object type from enrichment attribution
        attribution = data.get("attribution", {})
        object_type = attribution.get("object_type")

        # Use estimate from parsed fields or enrichment
        estimate_for_cost = None
        if parsed_record and parsed_record.estimate_low:
            estimate_for_cost = parsed_record.estimate_low
        elif auction.get("estimate_eur"):
            estimate_for_cost = auction["estimate_eur"]
        elif data.get("estimate_low"):
            estimate_for_cost = data["estimate_low"]

        # Get current bid from parsed fields
        current_bid_val = None
        if parsed_record and parsed_record.current_bid and parsed_record.current_bid > 0:
            current_bid_val = parsed_record.current_bid

        landed = compute_landed_cost(estimate_for_cost, object_type, seller_loc, current_bid_val)
        if landed:
            expl["landed_cost_estimate"] = landed
            expl["seller_location"] = seller_loc
            # Also compute expected resale for the API
            if isinstance(resale, dict) and resale.get("low") and resale.get("high"):
                expl["expected_resale_value"] = round((resale["low"] + resale["high"]) / 2)

        lot_scores.explanation_json = expl
        db.add(lot_scores)
        scored += 1

    db.commit()
    db.close()

    logger.info(f"Imported {imported} enrichments, scored {scored} lots")


if __name__ == "__main__":
    run()
