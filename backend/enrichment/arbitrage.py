"""Arbitrage scoring enrichment agent.

Uses the comparables matching engine to find relevant market data,
then computes value estimates and arbitrage scores.

Buy-side: HammerPredictor estimates what you'll pay (from historical Auctionet data).
Sell-side: ComparablesMatcher estimates resale value (from FINN, Blomqvist, Pamono, etc).
"""

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.comparables import ComparablesMatcher, ComparablesResult
from backend.config import load_yaml_config
from backend.enrichment.base import EnrichmentAgent
from backend.hammer_predictor import HammerPredictor, HammerPrediction

logger = logging.getLogger(__name__)


class ArbitrageAgent(EnrichmentAgent):
    """Agent for computing arbitrage and value assessment."""

    def __init__(self):
        """Initialize arbitrage agent."""
        super().__init__(
            agent_name="arbitrage",
            agent_version="v2",
            model_name=None,
        )
        resale_config = load_yaml_config("resale_costs.yaml")
        resale = resale_config.get("resale_arbitrage", {})
        self.buyer_premium_rate = resale.get("buyer_premium_rate", 0.20)
        self.vat_on_premium_rate = resale.get("vat_on_premium_rate", 0.25)
        self.transport = resale.get("transport", {})
        self.transport_location_multiplier = resale.get("transport_location_multiplier", {})
        self.import_vat_rate = resale.get("import", {}).get("import_vat_rate", 0.25)

    async def run(
        self,
        lot_id: int,
        input_data: dict[str, Any],
        db: Session,
    ) -> dict[str, Any]:
        """Run arbitrage analysis using comparables matching.

        Args:
            lot_id: ID of the lot
            input_data: Parsed fields, comparable data, etc
            db: Database session

        Returns:
            Arbitrage output with value estimates and score
        """
        logger.info(f"Running arbitrage analysis for lot {lot_id}")

        current_bid = input_data.get("current_bid")
        estimate_low = input_data.get("estimate_low")
        estimate_high = input_data.get("estimate_high")
        currency = input_data.get("currency", "SEK")

        # Find matching comparables (sell-side: what it's worth)
        matcher = ComparablesMatcher(db)
        result = matcher.find_comparables(lot_id, max_results=50, min_relevance=0.15)

        if not result.matches:
            return self._empty_output("No matching comparables found")

        # Predict hammer price (buy-side: what you'll pay)
        predictor = HammerPredictor(db)
        hammer_prediction = predictor.predict(lot_id)
        hammer_est = hammer_prediction.predicted_hammer

        # Fall back to old method if predictor has no data
        if not hammer_est:
            hammer_est = _estimate_hammer(current_bid, estimate_low, estimate_high)
        if not hammer_est:
            return self._empty_output("No price data to compute arbitrage")

        # Convert to EUR for comparison (comparables are in EUR)
        hammer_eur = _to_eur(hammer_est, currency)

        # Compute landed cost (hammer + premium + transport + VAT)
        premium = hammer_eur * self.buyer_premium_rate
        vat_on_premium = premium * self.vat_on_premium_rate
        transport = self._estimate_transport(input_data.get("object_type"), input_data.get("seller_location"))
        landed_cost = hammer_eur + premium + vat_on_premium + transport

        # Get value estimates from comparables (weighted by source reliability)
        expected_resale = result.expected_resale_value
        fair_low = result.fair_value_low
        fair_high = result.fair_value_high
        retail_new = result.retail_new_price

        # Compute arbitrage score
        arb_score = self._compute_score(landed_cost, expected_resale, result)

        # Compute bid ceiling: max you should bid to hit min multiplier
        max_bid_eur = self._compute_bid_ceiling(expected_resale, transport)

        # Build reasons
        reasons = self._build_reasons(result, hammer_eur, landed_cost, expected_resale, retail_new)

        # Add hammer prediction context
        if hammer_prediction.method in ("historical_match", "ratio_adjusted"):
            reasons.append(
                f"Hammer predicted from {hammer_prediction.num_matches} historical sales "
                f"(€{hammer_prediction.prediction_low:.0f}–€{hammer_prediction.prediction_high:.0f})"
            )
            if hammer_prediction.estimate_to_hammer_ratio:
                reasons.append(
                    f"Historical estimate→hammer ratio: {hammer_prediction.estimate_to_hammer_ratio:.2f}x"
                )

        # Underpriced detection
        if current_bid and hammer_prediction.predicted_hammer and hammer_prediction.method != "estimate_fallback":
            bid_eur = _to_eur(current_bid, currency)
            pred_eur = _to_eur(hammer_prediction.predicted_hammer, currency) if currency != "EUR" else hammer_prediction.predicted_hammer
            if pred_eur > 0:
                underpriced_ratio = bid_eur / pred_eur
                if underpriced_ratio < 0.6:
                    reasons.append(
                        f"🔥 Current bid €{bid_eur:.0f} is {underpriced_ratio:.0%} of predicted hammer €{pred_eur:.0f}"
                    )

        # Build risks
        risks = self._build_risks(result, landed_cost, expected_resale)
        if hammer_prediction.method == "estimate_fallback":
            risks.append("No historical hammer data — acquisition cost estimated from house estimate")

        # Top comparables for explanation — include value weight %
        from backend.comparables import SOURCE_VALUE_WEIGHT
        top_comps = [
            {
                "title": m.title[:100],
                "source": m.source_name,
                "price": m.sold_price,
                "tier": m.tier,
                "value_weight": SOURCE_VALUE_WEIGHT.get(m.tier, 0.4),
                "weighted_value": round(m.sold_price * SOURCE_VALUE_WEIGHT.get(m.tier, 0.4)) if m.sold_price else None,
                "relevance": round(m.relevance_score, 2),
                "signals": m.match_signals,
            }
            for m in result.matches[:10]
        ]

        output = {
            "fair_value_range": {"low": fair_low, "high": fair_high} if fair_low else None,
            "expected_resale_value": expected_resale,
            "landed_cost_estimate": round(landed_cost),
            "estimated_margin_range": {
                "low": round(fair_low - landed_cost) if fair_low else None,
                "high": round(fair_high - landed_cost) if fair_high else None,
            } if fair_low else None,
            "arbitrage_score": arb_score,
            "confidence": result.confidence,
            "reasons": reasons,
            "risks": risks,
            # Fields consumed by the scoring engine / lot cards
            "ai_value_low": fair_low,
            "ai_value_high": fair_high,
            "ai_value_basis": f"{len(result.matches)} comparables across {_tier_summary(result)}",
            "comparables_count": len(result.matches),
            "retail_new_price": retail_new,
            "top_comparables": top_comps,
            # Buy-side: hammer prediction from historical data
            "hammer_prediction": {
                "predicted": hammer_prediction.predicted_hammer,
                "low": hammer_prediction.prediction_low,
                "high": hammer_prediction.prediction_high,
                "confidence": hammer_prediction.confidence,
                "method": hammer_prediction.method,
                "num_historical_matches": hammer_prediction.num_matches,
                "estimate_to_hammer_ratio": hammer_prediction.estimate_to_hammer_ratio,
                "top_matches": hammer_prediction.matches[:5],
            },
            "max_bid_eur": max_bid_eur,
        }

        logger.info(
            f"Arbitrage lot {lot_id}: score={arb_score}, "
            f"comps={len(result.matches)}, resale={expected_resale}, landed={landed_cost:.0f}"
        )
        return output

    def _estimate_transport(self, object_type: Optional[str], seller_location: Optional[str] = None) -> float:
        """Estimate transport cost in EUR based on object type and seller location."""
        transport_sek = self.transport.get("medium_item", 3000)
        if object_type:
            t = object_type.lower()
            if any(w in t for w in ["sofa", "large", "sectional", "dining set"]):
                transport_sek = self.transport.get("oversized_item", 8000)
            elif any(w in t for w in ["table", "sideboard", "cabinet", "shelving", "chest"]):
                transport_sek = self.transport.get("large_item", 5000)
            elif any(w in t for w in ["lamp", "stool", "small"]):
                transport_sek = self.transport.get("small_item", 1500)

        # Apply location-based multiplier
        multiplier = _get_location_multiplier(seller_location, self.transport_location_multiplier)
        transport_sek *= multiplier

        return transport_sek / 11.49  # SEK to EUR

    def _compute_bid_ceiling(
        self,
        expected_resale: Optional[float],
        transport_eur: float,
        target_multiplier: float = 2.0,
    ) -> Optional[float]:
        """Compute maximum rational bid in EUR.

        max_bid = (resale / target_multiplier - transport) / (1 + premium * (1 + vat_on_premium))
        """
        if not expected_resale:
            return None
        target_landed = expected_resale / target_multiplier
        cost_per_eur_bid = 1.0 + self.buyer_premium_rate * (1.0 + self.vat_on_premium_rate)
        max_bid = (target_landed - transport_eur) / cost_per_eur_bid
        return round(max_bid) if max_bid > 0 else None

    def _compute_score(
        self,
        landed_cost: float,
        expected_resale: Optional[float],
        result: ComparablesResult,
    ) -> Optional[float]:
        """Compute arbitrage score (0-1).

        Based on resale multiplier with confidence adjustment.
        """
        if not expected_resale or landed_cost <= 0:
            return None

        multiplier = expected_resale / landed_cost

        # Map multiplier to score: <1.5x = 0, 2x = 0.5, 3x+ = 1.0
        if multiplier < 1.5:
            raw_score = 0.0
        elif multiplier >= 3.0:
            raw_score = 1.0
        else:
            raw_score = (multiplier - 1.5) / 1.5

        # Adjust by confidence
        return round(raw_score * result.confidence, 3)

    def _build_reasons(
        self,
        result: ComparablesResult,
        hammer_eur: float,
        landed_cost: float,
        expected_resale: Optional[float],
        retail_new: Optional[float],
    ) -> list[str]:
        reasons = []
        n = len(result.matches)
        reasons.append(f"Based on {n} comparable{'s' if n != 1 else ''}")

        if expected_resale and landed_cost > 0:
            mult = expected_resale / landed_cost
            reasons.append(f"Resale/cost ratio: {mult:.1f}x (landed €{landed_cost:.0f} → resale €{expected_resale:.0f})")

        if retail_new:
            discount = (1 - hammer_eur / retail_new) * 100
            reasons.append(f"Auction estimate is {discount:.0f}% below retail new (€{retail_new:.0f})")

        if result.resale_prices:
            lo, hi = min(result.resale_prices), max(result.resale_prices)
            reasons.append(f"Norwegian resale range: €{lo:.0f}–€{hi:.0f}")

        return reasons

    def _build_risks(
        self,
        result: ComparablesResult,
        landed_cost: float,
        expected_resale: Optional[float],
    ) -> list[str]:
        risks = []
        if result.confidence < 0.5:
            risks.append("Low confidence — few matching comparables")
        if expected_resale and landed_cost > 0 and expected_resale / landed_cost < 2.0:
            risks.append("Thin margin — resale multiplier below 2x target")
        if not result.resale_prices:
            risks.append("No Norwegian resale data — resale value estimated from dealer prices")
        risks.append("Transport cost estimated — actual may vary")
        return risks

    def _empty_output(self, reason: str) -> dict[str, Any]:
        return {
            "fair_value_range": None,
            "expected_resale_value": None,
            "landed_cost_estimate": None,
            "estimated_margin_range": None,
            "arbitrage_score": None,
            "confidence": None,
            "reasons": [reason],
            "risks": ["Insufficient data for valuation"],
            "ai_value_low": None,
            "ai_value_high": None,
            "ai_value_basis": None,
            "comparables_count": 0,
            "retail_new_price": None,
            "top_comparables": [],
            "hammer_prediction": None,
            "max_bid_eur": None,
        }


def _get_location_multiplier(seller_location: Optional[str], multiplier_map: dict) -> float:
    """Look up transport multiplier for a seller location.

    Tries exact city match first, then falls back to country-level default.
    """
    if not seller_location or not multiplier_map:
        return multiplier_map.get("_default_unknown", 1.5)

    # Exact match
    if seller_location in multiplier_map:
        return multiplier_map[seller_location]

    # Country fallback: extract country from "City, Country"
    parts = seller_location.rsplit(", ", 1)
    if len(parts) == 2:
        country = parts[1].strip()
        country_key = f"_default_{country}"
        if country_key in multiplier_map:
            return multiplier_map[country_key]

    return multiplier_map.get("_default_unknown", 1.5)


def _estimate_hammer(
    current_bid: Optional[float],
    estimate_low: Optional[float],
    estimate_high: Optional[float],
) -> Optional[float]:
    """Estimate likely hammer price from available data."""
    if current_bid and current_bid > 0:
        return current_bid
    if estimate_low and estimate_high:
        return (estimate_low + estimate_high) / 2
    return estimate_low or estimate_high


def _to_eur(amount: float, currency: str) -> float:
    """Convert to EUR using approximate rates."""
    rates = {
        "EUR": 1.0,
        "SEK": 0.087,
        "NOK": 0.085,
        "DKK": 0.134,
        "GBP": 1.17,
        "USD": 0.91,
    }
    return amount * rates.get(currency.upper(), 0.087)


def _tier_summary(result: ComparablesResult) -> str:
    """Build a short summary of which tiers are represented."""
    parts = []
    if result.retail_prices:
        parts.append(f"{len(result.retail_prices)} retail")
    if result.resale_prices:
        parts.append(f"{len(result.resale_prices)} NO resale")
    if result.dealer_prices:
        parts.append(f"{len(result.dealer_prices)} dealer")
    if result.auction_prices:
        parts.append(f"{len(result.auction_prices)} auction")
    return ", ".join(parts) or "no priced comps"
