"""Hammer price predictor using historical Auctionet data.

Predicts what you'll likely HAVE TO PAY (acquisition cost) for a lot
based on historical ended auction data. This is the BUY-SIDE of the
arbitrage equation — the SELL-SIDE (resale value) comes from ComparablesMatcher.

Key metrics:
- predicted_hammer: best estimate of final hammer price
- estimate_to_hammer_ratio: how much lots typically sell for vs their estimate
- max_bid: ceiling bid = (resale_value - costs) / (1 + premium + vat)
"""

import logging
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models import (
    HistoricalHammer,
    NormalizedLotFields,
    ParsedLotFields,
)

logger = logging.getLogger(__name__)


@dataclass
class HammerPrediction:
    """Predicted hammer price for a current lot."""

    predicted_hammer: Optional[float] = None       # Best estimate (EUR)
    prediction_low: Optional[float] = None         # P25 estimate (EUR)
    prediction_high: Optional[float] = None        # P75 estimate (EUR)
    confidence: float = 0.0                        # 0-1
    num_matches: int = 0
    estimate_to_hammer_ratio: Optional[float] = None  # Historical median ratio
    method: str = "no_data"                        # historical_match | ratio_adjusted | estimate_fallback | no_data
    matches: list[dict] = field(default_factory=list)  # Top matching historical lots


class HammerPredictor:
    """Predicts likely hammer price using historical Auctionet data."""

    # Matching weights (buy-side: designer matters most)
    WEIGHT_DESIGNER = 0.45
    WEIGHT_OBJECT_TYPE = 0.25
    WEIGHT_TITLE = 0.20
    WEIGHT_MATERIAL = 0.10

    def __init__(self, db: Session, max_age_days: int = 365):
        self.db = db
        self.max_age_days = max_age_days

    def predict(self, lot_id: int) -> HammerPrediction:
        """Predict hammer price for a current lot.

        Args:
            lot_id: ID of the active lot.

        Returns:
            HammerPrediction with estimated acquisition cost.
        """
        # Load lot data
        parsed = self.db.query(ParsedLotFields).filter(
            ParsedLotFields.lot_id == lot_id
        ).order_by(ParsedLotFields.created_at.desc()).first()

        if not parsed:
            return HammerPrediction()

        normalized = self.db.query(NormalizedLotFields).filter(
            NormalizedLotFields.lot_id == lot_id
        ).order_by(NormalizedLotFields.created_at.desc()).first()

        # Build lot profile
        lot_title = (parsed.title or "").lower()
        lot_object_type = normalized.object_type_id if normalized else None
        lot_materials = set(normalized.materials or []) if normalized else set()
        lot_designers = _parse_designers(parsed.raw_designer_mentions)
        estimate_mid = None
        if parsed.estimate_low and parsed.estimate_high:
            estimate_mid = (parsed.estimate_low + parsed.estimate_high) / 2
        elif parsed.estimate_low:
            estimate_mid = parsed.estimate_low

        # Load enrichment for richer matching
        from backend.comparables import _load_enrichment_json, _infer_object_type
        from backend.models import Lot
        lot = self.db.query(Lot).filter(Lot.id == lot_id).first()
        ext_id = lot.external_lot_id if lot else str(lot_id)
        enrichment = _load_enrichment_json(ext_id)

        if enrichment:
            e_designer = enrichment.get("designer", {})
            if isinstance(e_designer, dict) and e_designer.get("name"):
                name = e_designer["name"].lower()
                if name != "unknown" and name not in lot_designers:
                    lot_designers.append(name)
            if not lot_object_type and enrichment.get("object_type"):
                lot_object_type = enrichment["object_type"]
            if not lot_materials:
                for m in enrichment.get("materials", []):
                    if isinstance(m, str):
                        lot_materials.add(m.lower())
                    elif isinstance(m, dict) and m.get("material"):
                        lot_materials.add(m["material"].lower())

        if not lot_object_type:
            lot_object_type = _infer_object_type(parsed.category_raw, lot_title)

        # Find matching historical hammers
        candidates = self._query_candidates(lot_designers, lot_object_type, lot_title)

        if not candidates:
            return self._fallback(estimate_mid, parsed.current_bid)

        # Score each candidate
        scored = []
        for h in candidates:
            score = self._score_match(h, lot_designers, lot_object_type, lot_materials, lot_title)
            if score >= 0.20:
                scored.append((h, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:30]

        if not top:
            return self._fallback(estimate_mid, parsed.current_bid)

        return self._compute_prediction(top, estimate_mid, parsed.current_bid)

    def predict_from_fields(
        self,
        title: str,
        designers: list[str],
        object_type: Optional[str],
        materials: list[str],
        estimate_low: Optional[float],
        estimate_high: Optional[float],
        current_bid: Optional[float] = None,
    ) -> HammerPrediction:
        """Predict hammer price from raw fields (no lot_id needed).

        Useful for ad-hoc queries like "what do EA 208 chairs go for?"
        """
        lot_title = title.lower()
        lot_designers = [d.lower() for d in designers]
        lot_materials = {m.lower() for m in materials}

        estimate_mid = None
        if estimate_low and estimate_high:
            estimate_mid = (estimate_low + estimate_high) / 2
        elif estimate_low:
            estimate_mid = estimate_low

        candidates = self._query_candidates(lot_designers, object_type, lot_title)
        if not candidates:
            return self._fallback(estimate_mid, current_bid)

        scored = []
        for h in candidates:
            score = self._score_match(h, lot_designers, object_type, lot_materials, lot_title)
            if score >= 0.20:
                scored.append((h, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:30]

        if not top:
            return self._fallback(estimate_mid, current_bid)

        return self._compute_prediction(top, estimate_mid, current_bid)

    def _query_candidates(
        self,
        designers: list[str],
        object_type: Optional[str],
        title: str,
    ) -> list[HistoricalHammer]:
        """Query candidate historical hammers using broad filters."""
        from sqlalchemy import or_
        from datetime import datetime, timedelta

        filters = []
        cutoff = datetime.utcnow() - timedelta(days=self.max_age_days)

        # Match by designer name
        for d in designers[:3]:
            if len(d) > 3:
                filters.append(func.lower(HistoricalHammer.designer_name).contains(d))
                filters.append(func.lower(HistoricalHammer.title).contains(d))

        # Match by object type
        if object_type:
            related = _expand_type(object_type)
            filters.append(func.lower(HistoricalHammer.object_type).in_([t.lower() for t in related]))

        # Match by title keywords
        import re
        stop_words = {
            "with", "from", "and", "the", "for", "set", "pair",
            "circa", "style", "made", "model", "stol", "bord",
        }
        words = [w for w in re.split(r'\W+', title) if len(w) > 3 and w not in stop_words]
        for word in words[:4]:
            filters.append(func.lower(HistoricalHammer.title).contains(word))

        if not filters:
            return []

        return self.db.query(HistoricalHammer).filter(
            or_(*filters),
            HistoricalHammer.was_sold == 1,
            HistoricalHammer.hammer_price.isnot(None),
            HistoricalHammer.scraped_at >= cutoff,
        ).limit(200).all()

    def _score_match(
        self,
        h: HistoricalHammer,
        lot_designers: list[str],
        lot_object_type: Optional[str],
        lot_materials: set[str],
        lot_title: str,
    ) -> float:
        """Score how relevant a historical hammer is to a current lot."""
        score = 0.0

        # Designer match
        if h.designer_name and lot_designers:
            h_designer = h.designer_name.lower()
            for d in lot_designers:
                if d in h_designer or h_designer in d:
                    score += self.WEIGHT_DESIGNER
                    break
        elif lot_designers:
            h_title = (h.title or "").lower()
            for d in lot_designers:
                if len(d) > 3 and d in h_title:
                    score += self.WEIGHT_DESIGNER * 0.7
                    break

        # Object type match
        if lot_object_type and h.object_type:
            if lot_object_type.lower() == h.object_type.lower():
                score += self.WEIGHT_OBJECT_TYPE
            elif _types_related(lot_object_type.lower(), h.object_type.lower()):
                score += self.WEIGHT_OBJECT_TYPE * 0.5

        # Title similarity
        if lot_title and h.title:
            sim = SequenceMatcher(None, lot_title, h.title.lower()).ratio()
            if sim > 0.3:
                score += self.WEIGHT_TITLE * min(sim, 1.0)

        # Material match
        if lot_materials and h.materials:
            h_mats = set()
            if isinstance(h.materials, list):
                h_mats = {m.lower() for m in h.materials if isinstance(m, str)}
            if h_mats:
                overlap = lot_materials & h_mats
                if overlap:
                    score += self.WEIGHT_MATERIAL * min(len(overlap) / max(len(lot_materials), 1), 1.0)

        return round(score, 4)

    def _compute_prediction(
        self,
        scored: list[tuple[HistoricalHammer, float]],
        estimate_mid: Optional[float],
        current_bid: Optional[float],
    ) -> HammerPrediction:
        """Compute prediction from scored historical matches."""
        hammers = [h.hammer_price for h, _ in scored if h.hammer_price]

        if not hammers:
            return self._fallback(estimate_mid, current_bid)

        hammers_sorted = sorted(hammers)
        predicted = _median(hammers_sorted)
        p25 = _percentile(hammers_sorted, 25)
        p75 = _percentile(hammers_sorted, 75)

        # Compute estimate-to-hammer ratio
        ratios = []
        for h, _ in scored:
            if h.hammer_price and h.estimate_low and h.estimate_high:
                est_mid = (h.estimate_low + h.estimate_high) / 2
                if est_mid > 0:
                    ratios.append(h.hammer_price / est_mid)

        ratio = _median(sorted(ratios)) if ratios else None

        # If we have the current lot's estimate, blend direct + ratio prediction
        method = "historical_match"
        if ratio and estimate_mid and len(hammers) >= 3:
            ratio_prediction = estimate_mid * ratio
            # Blend: 60% direct median, 40% ratio-based
            predicted = predicted * 0.6 + ratio_prediction * 0.4
            method = "ratio_adjusted"

        # Confidence based on match count
        if len(hammers) >= 5:
            confidence = min(0.9, 0.4 + 0.1 * len(hammers))
        elif len(hammers) >= 2:
            confidence = 0.3 + 0.1 * len(hammers)
        else:
            confidence = 0.2

        # Build top matches for display
        top_matches = [
            {
                "title": h.title[:100] if h.title else "",
                "hammer_price": h.hammer_price,
                "estimate": (h.estimate_low + h.estimate_high) / 2 if h.estimate_low and h.estimate_high else None,
                "designer": h.designer_name,
                "relevance": round(s, 2),
                "auction_house": h.auction_house_name,
            }
            for h, s in scored[:8]
        ]

        return HammerPrediction(
            predicted_hammer=round(predicted),
            prediction_low=round(p25),
            prediction_high=round(p75),
            confidence=round(confidence, 2),
            num_matches=len(hammers),
            estimate_to_hammer_ratio=round(ratio, 2) if ratio else None,
            method=method,
            matches=top_matches,
        )

    def _fallback(
        self,
        estimate_mid: Optional[float],
        current_bid: Optional[float],
    ) -> HammerPrediction:
        """Fallback when no historical data is available."""
        if current_bid and current_bid > 0:
            return HammerPrediction(
                predicted_hammer=current_bid,
                confidence=0.15,
                method="estimate_fallback",
            )
        if estimate_mid:
            return HammerPrediction(
                predicted_hammer=estimate_mid,
                confidence=0.10,
                method="estimate_fallback",
            )
        return HammerPrediction()


def _expand_type(object_type: str) -> list[str]:
    """Get related object types for broader matching."""
    groups = {
        "chair": ["chair", "dining chair", "armchair", "office chair", "lounge chair"],
        "table": ["table", "dining table", "coffee table", "side table", "desk"],
        "cabinet": ["cabinet", "sideboard", "chest of drawers", "shelf", "shelving"],
        "sofa": ["sofa", "daybed", "bench"],
        "stool": ["stool", "barstool"],
        "lamp": ["lamp", "pendant", "floor lamp"],
    }
    for group in groups.values():
        if object_type.lower() in [t.lower() for t in group]:
            return group
    return [object_type]


def _types_related(type_a: str, type_b: str) -> bool:
    """Check if two object types are in the same family."""
    families = [
        {"chair", "dining chair", "armchair", "office chair", "lounge chair", "stool"},
        {"table", "dining table", "coffee table", "side table", "desk"},
        {"cabinet", "sideboard", "chest of drawers", "shelf", "shelving"},
        {"sofa", "daybed", "bench"},
    ]
    for family in families:
        if type_a in family and type_b in family:
            return True
    return False


def _parse_designers(raw: Optional[list]) -> list[str]:
    """Parse raw designer mentions from JSON field."""
    if not raw:
        return []
    if isinstance(raw, str):
        import json
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            return [raw.lower()] if raw else []
    return [d.lower() for d in raw if isinstance(d, str) and d.lower() != "unknown"]


def _median(values: list[float]) -> float:
    if not values:
        return 0
    n = len(values)
    mid = n // 2
    return values[mid] if n % 2 == 1 else (values[mid - 1] + values[mid]) / 2


def _percentile(values: list[float], pct: int) -> float:
    if not values:
        return 0
    k = (len(values) - 1) * pct / 100
    f = int(k)
    c = min(f + 1, len(values) - 1)
    return values[f] + (k - f) * (values[c] - values[f])
