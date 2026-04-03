"""Comparables matching engine.

Finds and ranks comparable sales/listings for a given lot using
multi-signal matching: entity, object type, materials, and title similarity.
"""

import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models import Comparable, Entity, NormalizedLotFields, ParsedLotFields

logger = logging.getLogger(__name__)

# Source type classification
RETAIL_SOURCES = {"Nordiska Galleriet", "Finnish Design Shop"}
RESALE_SOURCES = {"FINN.no"}
NORWAY_AUCTION_SOURCES = {"Blomqvist"}  # Norwegian hammer prices = best resale signal
DEALER_SOURCES = {"Pamono", "1stDibs", "Chairish", "Vinterior", "Selency"}

# How close each source's price is to the ACTUAL achievable resale value in Norway.
# 1.0 = price IS the resale value, 0.3 = price is a ceiling/reference only.
SOURCE_VALUE_WEIGHT = {
    # Norwegian auction hammer = closest to real value.
    # The buyer paid this + premium, so the item is "worth" at least this to a Norwegian buyer.
    "norway_auction": 0.95,
    # FINN.no asking prices: sellers list high, actual sale ~70-80% of asking after negotiation.
    "resale": 0.70,
    # International dealers: inflated by curation/shipping margins. Norwegian resale is ~50-60%.
    "dealer": 0.50,
    # Auction hammer (Sweden/international): lower market. Norwegian value is typically higher.
    "auction": 0.40,
    # New retail: secondhand is typically 25-35% of new for mid-century Scandinavian.
    "retail": 0.30,
}


def _source_tier(source_name: str) -> str:
    """Classify a source into a pricing tier."""
    if source_name in RETAIL_SOURCES:
        return "retail"
    if source_name in NORWAY_AUCTION_SOURCES:
        return "norway_auction"
    if source_name in RESALE_SOURCES:
        return "resale"
    if source_name in DEALER_SOURCES:
        return "dealer"
    s = source_name.lower()
    if any(w in s for w in ["auction", "auctionet", "lauritz", "bukowski", "barneby", "bruun"]):
        return "auction"
    if any(w in s for w in ["gumtree", "dba", "ebay", "finn"]):
        return "resale"
    return "dealer"


@dataclass
class MatchedComparable:
    """A comparable matched to a lot with relevance scoring."""
    comparable_id: int
    title: str
    source_name: str
    sold_price: Optional[float]
    currency: str
    object_type: Optional[str]
    tier: str  # retail, dealer, resale, auction
    relevance_score: float  # 0-1
    match_signals: list[str] = field(default_factory=list)


@dataclass
class ComparablesResult:
    """Result of matching comparables to a lot."""
    matches: list[MatchedComparable]
    retail_prices: list[float]
    resale_prices: list[float]
    dealer_prices: list[float]
    auction_prices: list[float]
    fair_value_low: Optional[float] = None
    fair_value_high: Optional[float] = None
    retail_new_price: Optional[float] = None
    expected_resale_value: Optional[float] = None
    weighted_resale_value: Optional[float] = None  # Weighted by source reliability
    confidence: float = 0.0


class ComparablesMatcher:
    """Matches comparables to lots using weighted multi-signal scoring."""

    # Signal weights for relevance scoring
    WEIGHT_ENTITY = 0.40
    WEIGHT_OBJECT_TYPE = 0.25
    WEIGHT_MATERIAL = 0.15
    WEIGHT_TITLE = 0.20

    def __init__(self, db: Session):
        self.db = db
        # Cache all entities for fast lookup
        self._entities = {
            e.id: e for e in db.query(Entity).all()
        }
        # Load source value weights from config (fall back to module defaults)
        try:
            from backend.config import load_yaml_config
            resale_config = load_yaml_config("resale_costs.yaml")
            cfg_weights = resale_config.get("resale_arbitrage", {}).get("source_value_weights", {})
            if cfg_weights:
                SOURCE_VALUE_WEIGHT.update(cfg_weights)
        except Exception:
            pass  # Use module-level defaults

    def find_comparables(
        self,
        lot_id: int,
        max_results: int = 50,
        min_relevance: float = 0.15,
    ) -> ComparablesResult:
        """Find and rank comparables for a lot.

        Uses normalized fields (entity, object_type, materials) and parsed
        fields (title, designer mentions) to match against the comparables DB.

        Args:
            lot_id: Lot to find comparables for
            max_results: Maximum comparables to return
            min_relevance: Minimum relevance score (0-1)

        Returns:
            ComparablesResult with matched comparables and value estimates
        """
        # Get lot data
        normalized = self.db.query(NormalizedLotFields).filter(
            NormalizedLotFields.lot_id == lot_id
        ).order_by(NormalizedLotFields.created_at.desc()).first()

        parsed = self.db.query(ParsedLotFields).filter(
            ParsedLotFields.lot_id == lot_id
        ).order_by(ParsedLotFields.created_at.desc()).first()

        if not parsed:
            return ComparablesResult(matches=[])

        # Build lot profile — layer data: normalized > enrichment JSON > parsed
        lot_entity_id = normalized.designer_entity_id if normalized else None
        lot_producer_id = normalized.producer_entity_id if normalized else None
        lot_object_type = normalized.object_type_id if normalized else None
        lot_materials = set(normalized.materials or []) if normalized else set()
        lot_title = (parsed.title or "").lower()

        # Parse designer mentions (stored as JSON strings)
        raw_designers = _parse_json_field(parsed.raw_designer_mentions)
        lot_designers = [d.lower() for d in raw_designers if d and d.lower() != "unknown"]

        # Load enrichment JSON for richer data (designer, manufacturer, model, materials)
        # Enrichment files are keyed by external_lot_id
        from backend.models import Lot
        lot = self.db.query(Lot).filter(Lot.id == parsed.lot_id).first()
        ext_id = lot.external_lot_id if lot else str(parsed.lot_id)
        enrichment = _load_enrichment_json(ext_id)
        lot_manufacturer = None
        lot_model = None
        extra_search_terms = []

        if enrichment:
            # Designer from enrichment
            e_designer = enrichment.get("designer", {})
            if isinstance(e_designer, dict) and e_designer.get("name"):
                name = e_designer["name"]
                if name.lower() != "unknown" and name.lower() not in lot_designers:
                    lot_designers.append(name.lower())

            # Manufacturer from enrichment
            e_mfr = enrichment.get("manufacturer", {})
            if isinstance(e_mfr, dict) and e_mfr.get("name"):
                lot_manufacturer = e_mfr["name"]

            # Model name from enrichment
            e_model = enrichment.get("model", {})
            if isinstance(e_model, dict):
                lot_model = e_model.get("name_or_number") or e_model.get("name")

            # Object type from enrichment (more precise than parsed)
            if not lot_object_type and enrichment.get("object_type"):
                lot_object_type = enrichment["object_type"]

            # Materials from enrichment
            if not lot_materials:
                e_mats = enrichment.get("materials", [])
                for m in e_mats:
                    if isinstance(m, str):
                        lot_materials.add(m.lower())
                    elif isinstance(m, dict) and m.get("material"):
                        lot_materials.add(m["material"].lower())

            # AI-generated search terms (improvement #4)
            extra_search_terms = enrichment.get("comparable_search_terms", [])

        # If no entity link, try to resolve designer mentions to entities
        if not lot_entity_id and lot_designers:
            from sqlalchemy import func as sqlfunc
            for d in lot_designers:
                entity = self.db.query(Entity).filter(
                    sqlfunc.lower(Entity.canonical_name) == d
                ).first()
                if entity:
                    lot_entity_id = entity.id
                    break

        # Also try manufacturer as entity
        if not lot_entity_id and lot_manufacturer:
            from sqlalchemy import func as sqlfunc
            entity = self.db.query(Entity).filter(
                sqlfunc.lower(Entity.canonical_name) == lot_manufacturer.lower()
            ).first()
            if entity:
                lot_producer_id = entity.id

        # Infer object type from category_raw or title if still not set
        if not lot_object_type:
            lot_object_type = _infer_object_type(
                parsed.category_raw, lot_title
            )

        # Parse materials from parsed fields if still empty
        if not lot_materials:
            raw_mats = _parse_json_field(parsed.raw_material_mentions)
            lot_materials = {m.lower() if isinstance(m, str) else str(m).lower() for m in raw_mats}

        # Query comparables — start broad, score later
        candidates = self._query_candidates(
            lot_entity_id, lot_producer_id, lot_object_type,
            lot_title, lot_designers, lot_manufacturer, lot_model,
            extra_search_terms,
        )

        # Score each candidate
        scored = []
        for comp in candidates:
            score, signals = self._score_match(
                comp, lot_entity_id, lot_producer_id,
                lot_object_type, lot_materials, lot_title, lot_designers,
            )
            if score >= min_relevance:
                scored.append(MatchedComparable(
                    comparable_id=comp.id,
                    title=comp.title,
                    source_name=comp.source_name,
                    sold_price=comp.sold_price,
                    currency=comp.currency or "EUR",
                    object_type=comp.object_type,
                    tier=_source_tier(comp.source_name),
                    relevance_score=score,
                    match_signals=signals,
                ))

        # Sort by relevance, take top N
        scored.sort(key=lambda m: m.relevance_score, reverse=True)
        top_matches = scored[:max_results]

        # Compute value estimates from matches
        result = self._compute_values(top_matches)
        result.matches = top_matches
        return result

    def _query_candidates(
        self,
        entity_id: Optional[int],
        producer_id: Optional[int],
        object_type: Optional[str],
        title: str,
        designer_mentions: list[str],
        manufacturer: Optional[str] = None,
        model_name: Optional[str] = None,
        extra_search_terms: Optional[list[str]] = None,
    ) -> list[Comparable]:
        """Query candidate comparables using broad filters.

        We cast a wide net here and do fine-grained scoring later.
        """
        from sqlalchemy import or_

        filters = []

        # Match by entity (designer or producer)
        if entity_id:
            filters.append(Comparable.entity_id == entity_id)
        if producer_id and producer_id != entity_id:
            filters.append(Comparable.entity_id == producer_id)

        # Match by object type
        if object_type:
            related_types = self._expand_type(object_type)
            filters.append(func.lower(Comparable.object_type).in_([t.lower() for t in related_types]))

        # Match by manufacturer name in comparable titles
        if manufacturer and len(manufacturer) > 3:
            filters.append(func.lower(Comparable.title).contains(manufacturer.lower()))

        # Match by model name/number in comparable titles
        if model_name and len(str(model_name)) > 1:
            model_str = str(model_name).lower()
            filters.append(func.lower(Comparable.title).contains(model_str))

        # Match by AI-generated search terms
        for term in (extra_search_terms or [])[:5]:
            if len(term) > 3:
                filters.append(func.lower(Comparable.title).contains(term.lower()))

        # Match by title keywords (significant words from lot title)
        stop_words = {
            "with", "from", "and", "the", "for", "set", "pair",
            "circa", "style", "made", "model", "type", "piece", "pieces",
            "stol", "bord", "møbler", "furniture", "century", "denmark",
            "sweden", "second", "half", "attributed",
        }
        title_words = [
            w for w in re.split(r'\W+', title.lower())
            if len(w) > 3 and w not in stop_words
        ]
        for word in title_words[:5]:
            filters.append(func.lower(Comparable.title).contains(word))

        # Match by designer names in title
        for designer in designer_mentions[:3]:
            if len(designer) > 3:
                filters.append(func.lower(Comparable.title).contains(designer.lower()))

        if not filters:
            # Last resort: match on object type alone if we inferred one
            if object_type:
                return self.db.query(Comparable).filter(
                    func.lower(Comparable.object_type).in_(
                        [t.lower() for t in self._expand_type(object_type)]
                    )
                ).limit(300).all()
            return []

        # Use OR to cast a wide net — scoring handles precision
        results = self.db.query(Comparable).filter(
            or_(*filters)
        ).limit(500).all()

        # If entity/designer match gave few results, supplement with type-only matches
        if len(results) < 10 and object_type:
            type_matches = self.db.query(Comparable).filter(
                func.lower(Comparable.object_type).in_(
                    [t.lower() for t in self._expand_type(object_type)]
                )
            ).limit(200).all()
            seen = {r.id for r in results}
            for m in type_matches:
                if m.id not in seen:
                    results.append(m)
                    seen.add(m.id)

        return results

    def _score_match(
        self,
        comp: Comparable,
        lot_entity_id: Optional[int],
        lot_producer_id: Optional[int],
        lot_object_type: Optional[str],
        lot_materials: set[str],
        lot_title: str,
        lot_designers: list[str],
    ) -> tuple[float, list[str]]:
        """Score how relevant a comparable is to a lot.

        Returns (score 0-1, list of matching signal descriptions).
        """
        score = 0.0
        signals = []

        # 1. Entity match (designer/producer)
        if comp.entity_id and (comp.entity_id == lot_entity_id or comp.entity_id == lot_producer_id):
            entity = self._entities.get(comp.entity_id)
            name = entity.canonical_name if entity else "entity"
            score += self.WEIGHT_ENTITY
            signals.append(f"designer:{name}")
        elif lot_designers:
            # Fuzzy designer match in title
            comp_title_lower = comp.title.lower()
            for d in lot_designers:
                if len(d) > 3 and d in comp_title_lower:
                    score += self.WEIGHT_ENTITY * 0.7
                    signals.append(f"designer_fuzzy:{d}")
                    break

        # 2. Object type match
        if lot_object_type and comp.object_type:
            lot_type = lot_object_type.lower()
            comp_type = comp.object_type.lower()
            if lot_type == comp_type:
                score += self.WEIGHT_OBJECT_TYPE
                signals.append(f"type_exact:{comp_type}")
            elif self._types_related(lot_type, comp_type):
                score += self.WEIGHT_OBJECT_TYPE * 0.5
                signals.append(f"type_related:{comp_type}")

        # 3. Material overlap
        if lot_materials and comp.material_tags:
            comp_mats = set()
            if isinstance(comp.material_tags, list):
                comp_mats = {m.lower() if isinstance(m, str) else str(m).lower() for m in comp.material_tags}
            elif isinstance(comp.material_tags, str):
                import json
                try:
                    parsed = json.loads(comp.material_tags)
                    comp_mats = {m.lower() if isinstance(m, str) else str(m).lower() for m in parsed}
                except (json.JSONDecodeError, TypeError):
                    pass

            if comp_mats:
                overlap = lot_materials & comp_mats
                if overlap:
                    ratio = len(overlap) / max(len(lot_materials), 1)
                    score += self.WEIGHT_MATERIAL * min(ratio, 1.0)
                    signals.append(f"materials:{','.join(sorted(overlap))}")

        # 4. Title similarity
        if lot_title and comp.title:
            sim = SequenceMatcher(None, lot_title, comp.title.lower()).ratio()
            if sim > 0.3:
                score += self.WEIGHT_TITLE * min(sim, 1.0)
                if sim > 0.5:
                    signals.append(f"title_sim:{sim:.0%}")

        # Boost by comparable confidence
        comp_confidence = comp.confidence or 0.5
        score *= (0.5 + 0.5 * comp_confidence)

        return round(score, 4), signals

    def _expand_type(self, object_type: str) -> list[str]:
        """Get all related types for a given object type."""
        type_groups = {
            "chair": ["chair", "dining chair", "armchair", "office chair", "lounge chair", "rocking chair"],
            "table": ["table", "dining table", "coffee table", "side table", "desk", "dining table set with extension leaves"],
            "cabinet": ["cabinet", "sideboard", "chest of drawers", "high sideboard", "shelf", "wall-mounted shelving system", "wall shelving system"],
            "sofa": ["sofa", "seating set", "seating set (sofa and armchair)", "daybed"],
            "stool": ["stool", "barstool", "bench"],
            "lamp": ["lamp", "lighting", "pendant", "floor lamp"],
        }
        for group_types in type_groups.values():
            if object_type.lower() in [t.lower() for t in group_types]:
                return group_types
        return [object_type]

    def _types_related(self, type_a: str, type_b: str) -> bool:
        """Check if two object types are in the same family."""
        families = [
            {"chair", "dining chair", "armchair", "office chair", "lounge chair", "rocking chair", "stool", "barstool"},
            {"table", "dining table", "coffee table", "side table", "desk", "nesting tables", "dining table set with extension leaves"},
            {"cabinet", "sideboard", "chest of drawers", "high sideboard", "shelf", "wall-mounted shelving system", "wall shelving system", "shelving"},
            {"sofa", "seating set", "daybed", "bench"},
        ]
        for family in families:
            if type_a in family and type_b in family:
                return True
        return False

    def _compute_values(self, matches: list[MatchedComparable]) -> ComparablesResult:
        """Compute value estimates from matched comparables."""
        retail = [m.sold_price for m in matches if m.tier == "retail" and m.sold_price]
        norway_auction = [m.sold_price for m in matches if m.tier == "norway_auction" and m.sold_price]
        resale = [m.sold_price for m in matches if m.tier == "resale" and m.sold_price]
        dealer = [m.sold_price for m in matches if m.tier == "dealer" and m.sold_price]
        auction = [m.sold_price for m in matches if m.tier == "auction" and m.sold_price]

        result = ComparablesResult(
            matches=[],
            retail_prices=sorted(retail),
            resale_prices=sorted(norway_auction + resale),
            dealer_prices=sorted(dealer),
            auction_prices=sorted(auction),
        )

        # Retail new price: median of retail matches
        if retail:
            result.retail_new_price = _median(retail)

        # Compute weighted resale value: each source's price × its reliability weight
        # gives "what this item is likely worth on the Norwegian resale market"
        weighted_values = []
        weighted_weights = []
        for m in matches:
            if m.sold_price and m.sold_price > 0:
                w = SOURCE_VALUE_WEIGHT.get(m.tier, 0.4)
                # Also factor in match relevance — a 0.9 relevance match counts more
                effective_weight = w * m.relevance_score
                weighted_values.append(m.sold_price * w)
                weighted_weights.append(effective_weight)

        if weighted_values and sum(weighted_weights) > 0:
            result.weighted_resale_value = round(
                sum(v * w for v, w in zip(weighted_values, weighted_weights))
                / sum(w * w for w in weighted_weights)
            )

        # Expected resale value: prefer weighted calculation, fall back to tier-based
        if result.weighted_resale_value:
            result.expected_resale_value = result.weighted_resale_value
        elif norway_auction:
            result.expected_resale_value = _median(norway_auction)
        elif resale:
            result.expected_resale_value = round(_median(resale) * 0.75)
        elif dealer:
            result.expected_resale_value = round(_median(dealer) * 0.50)
        elif retail:
            result.expected_resale_value = round(_median(retail) * 0.30)

        # Fair value range: P25-P75 across resale + dealer prices
        all_market = sorted(resale + dealer)
        if all_market:
            result.fair_value_low = _percentile(all_market, 25)
            result.fair_value_high = _percentile(all_market, 75)
        elif retail:
            result.fair_value_low = round(_percentile(retail, 25) * 0.3)
            result.fair_value_high = round(_percentile(retail, 75) * 0.5)

        # Confidence based on match quantity and quality
        n = len(matches)
        has_entity = any("designer:" in s for m in matches for s in m.match_signals)
        tier_count = sum(1 for t in [retail, resale, dealer, auction] if t)

        if n >= 10 and has_entity and tier_count >= 2:
            result.confidence = 0.9
        elif n >= 5 and has_entity:
            result.confidence = 0.7
        elif n >= 3:
            result.confidence = 0.5
        elif n >= 1:
            result.confidence = 0.3
        else:
            result.confidence = 0.0

        return result


def _parse_json_field(val) -> list:
    """Parse a JSON field that may be a string, list, or None."""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        import json as _json
        try:
            parsed = _json.loads(val)
            return parsed if isinstance(parsed, list) else [parsed] if parsed else []
        except (ValueError, TypeError):
            return [val] if val else []
    return []


def _load_enrichment_json(external_lot_id: str) -> Optional[dict]:
    """Load enrichment JSON data for a lot from the data/enrichments/ directory."""
    from pathlib import Path
    enrichment_path = Path("data/enrichments") / f"{external_lot_id}.json"
    if not enrichment_path.exists():
        return None
    try:
        import json as _json
        return _json.loads(enrichment_path.read_text())
    except Exception:
        return None


def _infer_object_type(category_raw: Optional[str], title: str) -> Optional[str]:
    """Infer canonical object type from category text or title."""
    text = f"{category_raw or ''} {title}".lower()
    mappings = [
        ("barstool", ["barstool", "bar stool", "barkrakk"]),
        ("armchair", ["armchair", "lenestol", "lounge chair", "fåtölj", "easy chair", "wing chair"]),
        ("dining chair", ["dining chair", "spisestol", "side chair"]),
        ("chair", ["chair", "stol", "stool", "krakk"]),
        ("sofa", ["sofa", "couch", "settee", "daybed", "seating set"]),
        ("dining table", ["dining table", "spisebord", "extending table", "extendable table"]),
        ("coffee table", ["coffee table", "salongbord", "side table", "sidebord", "nesting table"]),
        ("table", ["table", "bord", "desk", "skrivebord"]),
        ("wall-mounted shelving system", ["shelving", "shelf", "hylle", "hyllesystem", "wall shelf", "bookcase"]),
        ("sideboard", ["sideboard", "cabinet", "cupboard", "chest", "credenza", "skap", "skjenk", "kommode"]),
        ("lighting", ["lamp", "light", "pendant", "chandelier", "lampe", "belysning"]),
    ]
    for obj_type, keywords in mappings:
        if any(kw in text for kw in keywords):
            return obj_type
    return None


def _median(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    if n == 0:
        return 0
    mid = n // 2
    return s[mid] if n % 2 == 1 else round((s[mid - 1] + s[mid]) / 2)


def _percentile(values: list[float], pct: int) -> float:
    s = sorted(values)
    k = (len(s) - 1) * pct / 100
    f = int(k)
    c = f + 1 if f + 1 < len(s) else f
    return round(s[f] + (k - f) * (s[c] - s[f]))
