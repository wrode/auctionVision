"""Scoring engine for lot evaluation."""

import json
import logging
import statistics
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.config import load_yaml_config
from backend.models import (
    Lot,
    LotScores,
    ParsedLotFields,
    EnrichmentOutput,
    FinnMarketData,
    FinnForSaleListing,
    HistoricalHammer,
    WantedListing,
)

logger = logging.getLogger(__name__)


def _parse_json_list(value) -> list:
    """Safely parse a JSON column that SQLite may return as a string."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []


class ScoringEngine:
    """Engine for computing lot scores."""

    def __init__(self):
        """Initialize scoring engine."""
        # Load scoring weights from config
        self.config = load_yaml_config("scoring.yaml")
        self.version = self.config.get("version", "v1")
        self.weights = self.config.get("weights", {})
        # Load resale multiplier rules
        filters = self.config.get("filters", {})
        self.min_resale_multiplier = filters.get("min_resale_multiplier", 2.0)
        self.preferred_resale_multiplier = filters.get("preferred_resale_multiplier", 3.0)
        # Load cost assumptions
        resale_config = load_yaml_config("resale_costs.yaml")
        resale = resale_config.get("resale_arbitrage", {})
        self.buyer_premium_rate = resale.get("buyer_premium_rate", 0.20)

    def compute_lot_scores(self, lot_id: int, db: Session) -> Optional[LotScores]:
        """Compute all scores for a lot.

        Args:
            lot_id: ID of the lot
            db: Database session

        Returns:
            LotScores record or None if failed
        """
        lot = db.query(Lot).filter(Lot.id == lot_id).first()
        if not lot:
            logger.warning(f"Lot {lot_id} not found")
            return None

        try:
            # Get parsed fields — prefer the record with the richest data.
            # Multiple parses may exist; later ones sometimes lose designer
            # mentions, so query for one with designers first, then fall back.
            all_parsed = (
                db.query(ParsedLotFields)
                .filter(ParsedLotFields.lot_id == lot_id)
                .order_by(ParsedLotFields.created_at.desc())
                .all()
            )
            parsed = None
            for candidate in all_parsed:
                designers = _parse_json_list(candidate.raw_designer_mentions)
                if designers and any(d and d != "Unknown" for d in designers):
                    parsed = candidate
                    break
            if parsed is None and all_parsed:
                parsed = all_parsed[0]  # fall back to latest

            # Get enrichment outputs
            arbitrage_output = self._get_enrichment_output(lot_id, "arbitrage", db)
            taste_output = self._get_enrichment_output(lot_id, "taste", db)
            wildcard_output = self._get_enrichment_output(lot_id, "wildcard", db)

            # Compute scores
            arbitrage_score = self._compute_arbitrage_score(arbitrage_output)
            resale_arb_score = self._compute_resale_arb_score(arbitrage_output)
            taste_score = self._compute_taste_score(taste_output)
            wildcard_score = self._compute_wildcard_score(wildcard_output)
            urgency_score = self._compute_urgency_score(parsed)
            demand_score, demand_matches = self._compute_demand_score(parsed, db)
            overall_watch_score = self._compute_overall_watch_score(
                arbitrage_score, taste_score, wildcard_score, urgency_score, demand_score
            )

            # Create or update scores record
            scores = db.query(LotScores).filter(LotScores.lot_id == lot_id).first()
            if not scores:
                scores = LotScores(lot_id=lot_id)

            scores.scoring_version = self.version
            scores.arbitrage_score = arbitrage_score
            scores.resale_arb_score = resale_arb_score
            scores.taste_score = taste_score
            scores.wildcard_score = wildcard_score
            scores.urgency_score = urgency_score
            scores.demand_score = demand_score
            scores.overall_watch_score = overall_watch_score
            scores.explanation_json = {
                "arbitrage_output": arbitrage_output,
                "taste_output": taste_output,
                "wildcard_output": wildcard_output,
                "demand_matches": demand_matches,
                # Surface comparables data for lot cards
                "ai_value_low": arbitrage_output.get("ai_value_low") if arbitrage_output else None,
                "ai_value_high": arbitrage_output.get("ai_value_high") if arbitrage_output else None,
                "ai_value_basis": arbitrage_output.get("ai_value_basis") if arbitrage_output else None,
                "landed_cost_estimate": arbitrage_output.get("landed_cost_estimate") if arbitrage_output else None,
                "expected_resale_value": arbitrage_output.get("expected_resale_value") if arbitrage_output else None,
                "comparables_count": arbitrage_output.get("comparables_count") if arbitrage_output else None,
                "retail_new_price": arbitrage_output.get("retail_new_price") if arbitrage_output else None,
            }

            db.add(scores)
            db.commit()
            db.refresh(scores)

            logger.info(f"Computed scores for lot {lot_id}: {overall_watch_score:.2f}")
            return scores

        except Exception as e:
            logger.error(f"Error computing scores for lot {lot_id}: {e}")
            return None

    def _get_enrichment_output(
        self,
        lot_id: int,
        agent_name: str,
        db: Session,
    ) -> Optional[dict[str, Any]]:
        """Get latest enrichment output for an agent.

        Args:
            lot_id: ID of the lot
            agent_name: Name of the agent
            db: Database session

        Returns:
            Output JSON or None
        """
        output = db.query(EnrichmentOutput).join(
            EnrichmentOutput.enrichment_run
        ).filter(
            EnrichmentOutput.lot_id == lot_id,
        ).filter_by(
            agent_name=agent_name,
        ).order_by(EnrichmentOutput.created_at.desc()).first()

        return output.output_json if output else None

    def _compute_arbitrage_score(self, arbitrage_output: Optional[dict]) -> Optional[float]:
        """Compute arbitrage score from enrichment output.

        Args:
            arbitrage_output: Arbitrage enrichment output

        Returns:
            Score 0-1 or None
        """
        if not arbitrage_output:
            return None

        # Use score from output if available
        return arbitrage_output.get("arbitrage_score")

    def _compute_resale_arb_score(self, arbitrage_output: Optional[dict]) -> Optional[float]:
        """Compute resale arbitrage score based on resale multiplier.

        Uses the rule: expected_resale / total_acquisition >= 2x (min) to 3x+ (strong).
        Score maps the multiplier onto 0-1: below 2x = 0, 2x = 0.5, 3x+ = 1.0.

        Args:
            arbitrage_output: Arbitrage enrichment output

        Returns:
            Score 0-1 or None
        """
        if not arbitrage_output:
            return None

        resale_value = arbitrage_output.get("expected_resale_value")
        acquisition = arbitrage_output.get("landed_cost_estimate")

        if resale_value and acquisition and acquisition > 0:
            multiplier = resale_value / acquisition
            if multiplier < self.min_resale_multiplier:
                return 0.0
            if multiplier >= self.preferred_resale_multiplier:
                return 1.0
            # Linear scale between min (2x → 0.5) and preferred (3x → 1.0)
            return 0.5 + 0.5 * (multiplier - self.min_resale_multiplier) / (
                self.preferred_resale_multiplier - self.min_resale_multiplier
            )

        # Fallback to raw score if no multiplier data yet
        return arbitrage_output.get("arbitrage_score")

    def _compute_taste_score(self, taste_output: Optional[dict]) -> Optional[float]:
        """Compute taste score from enrichment output.

        Args:
            taste_output: Taste enrichment output

        Returns:
            Score 0-1 or None
        """
        if not taste_output:
            return None

        return taste_output.get("taste_score")

    def _compute_wildcard_score(self, wildcard_output: Optional[dict]) -> Optional[float]:
        """Compute wildcard score from enrichment output.

        Args:
            wildcard_output: Wildcard enrichment output

        Returns:
            Score 0-1 or None
        """
        if not wildcard_output:
            return None

        return wildcard_output.get("wildcard_score")

    def _compute_urgency_score(self, parsed: Optional[ParsedLotFields]) -> Optional[float]:
        """Compute urgency score based on time remaining.

        Args:
            parsed: Parsed lot fields

        Returns:
            Score 0-1 or None
        """
        if not parsed or not parsed.auction_end_time:
            return None

        now = datetime.utcnow()
        if parsed.auction_end_time < now:
            return 0.0  # Auction ended

        # Calculate hours remaining
        hours_left = (parsed.auction_end_time - now).total_seconds() / 3600

        # Linear decay: 1.0 at <1 hour, 0.5 at ~6 hours, 0.0 at >24 hours
        if hours_left < 1:
            return 1.0
        elif hours_left < 6:
            return max(0.5, 1.0 - (hours_left - 1) / 10)
        else:
            return max(0.0, 1.0 - hours_left / 24)

    # ------------------------------------------------------------------
    # Demand score: composite signal from Finn wanted + historical data
    # ------------------------------------------------------------------

    def _compute_demand_score(
        self,
        parsed: Optional[ParsedLotFields],
        db: Session,
    ) -> tuple[Optional[float], dict]:
        """Compute a multi-dimensional demand signal.

        Combines three data sources:
        1. Finn wanted listings (forward-looking demand from real buyers)
        2. Historical hammer data (proven past demand for similar items)
        3. Finn for-sale supply data (market structure & resale benchmarks)

        Returns:
            Tuple of (score 0-1 or None, explanation dict)
        """
        if not parsed or not parsed.title:
            return None, {}

        # --- Finn wanted signal ---
        finn_score, finn_matches = self._finn_wanted_signal(parsed, db)

        # --- Historical flow signal ---
        hist_score, hist_details = self._historical_flow_signal(parsed, db)

        # --- Resale confidence signal (replaces finn_supply) ---
        resale_score, resale_details = self._resale_confidence_signal(parsed, db)

        # --- Combine ---
        # Weights: 30% Finn wanted (forward demand), 35% historical (proven
        # demand), 35% resale confidence (market structure & resale benchmark).
        # If one or more sources have no data, redistribute weight to the
        # remaining sources.
        scores: list[tuple[str, float, float]] = []
        if finn_score is not None:
            scores.append(("finn_wanted", finn_score, 0.30))
        if hist_score is not None:
            scores.append(("historical", hist_score, 0.35))
        if resale_score is not None:
            scores.append(("resale_confidence", resale_score, 0.35))

        if not scores:
            return None, {}

        # Normalize weights if only a subset of sources is available
        total_weight = sum(w for _, _, w in scores)
        combined = sum(s * w / total_weight for _, s, w in scores)

        explanation: dict[str, Any] = {
            "finn_matches": finn_matches,
            "finn_score": finn_score,
            "historical": hist_details,
            "historical_score": hist_score,
            "resale_confidence": resale_details,
            "resale_confidence_score": resale_score,
            "combined_method": [name for name, _, _ in scores],
        }

        return min(combined, 1.0), explanation

    # ------------------------------------------------------------------
    # Sub-signal 1: Finn wanted listings
    # ------------------------------------------------------------------

    def _finn_wanted_signal(
        self,
        parsed: ParsedLotFields,
        db: Session,
    ) -> tuple[Optional[float], list[dict]]:
        """Score based on matching Finn 'oenskes kjoept' listings.

        Returns:
            Tuple of (score 0-1 or None, list of match dicts)
        """
        lot_text = (parsed.title or "").lower()
        lot_designers = [d.lower() for d in _parse_json_list(parsed.raw_designer_mentions)]

        wanted = (
            db.query(WantedListing)
            .filter(
                WantedListing.status == "active",
                WantedListing.is_high_value == 1,
            )
            .all()
        )

        if not wanted:
            return None, []

        now = datetime.utcnow()
        matches: list[dict] = []

        for w in wanted:
            w_title = w.title.lower()

            # Check designer overlap: lot designer mentions appear in wanted title
            matched = False
            for designer in lot_designers:
                if len(designer) > 3 and designer in w_title:
                    matches.append(self._build_finn_match(w, "designer", designer, now))
                    matched = True
                    break

            # Check keyword overlap (significant words > 4 chars)
            if not matched:
                lot_words = set(
                    word
                    for word in lot_text.split()
                    if len(word) > 4
                    and word
                    not in {
                        "chair", "table", "stool", "light", "shelf",
                        "stol", "bord", "lampe", "hylle", "skap",
                        "ønskes", "kjøpt", "kjøpe", "ønsker",
                    }
                )
                w_words = set(word for word in w_title.split() if len(word) > 4)
                overlap = lot_words & w_words
                if len(overlap) >= 2:
                    matches.append(
                        self._build_finn_match(
                            w, "keyword", ", ".join(sorted(overlap)), now
                        )
                    )

        if not matches:
            # --- Category-level demand fallback ---
            inferred_category = self._infer_finn_category(lot_text)
            if inferred_category:
                category_count = (
                    db.query(WantedListing)
                    .filter(
                        WantedListing.status == "active",
                        WantedListing.category == inferred_category,
                    )
                    .count()
                )
                if category_count >= 400:
                    cat_score = 0.15
                elif category_count >= 200:
                    cat_score = 0.10
                elif category_count >= 50:
                    cat_score = 0.05
                else:
                    cat_score = 0.0

                if cat_score > 0.0:
                    return cat_score, [
                        {
                            "match_type": "category_demand",
                            "category": inferred_category,
                            "wanted_count": category_count,
                        }
                    ]

            return 0.0, []

        # --- Base score from match count ---
        n = len(matches)
        if n >= 4:
            score = 0.8
        elif n >= 2:
            score = 0.6
        else:
            score = 0.4

        # --- Boost: offered price vs lot estimate ---
        lot_estimate = parsed.estimate_low or parsed.current_bid or 0
        if lot_estimate > 0:
            max_offered = max(
                (m.get("offered_price") or 0) for m in matches
            )
            # NOK ~= SEK for simplicity
            if max_offered > 2 * lot_estimate:
                score += 0.1

        # --- Boost: freshness (any match seen in last 7 days) ---
        if any(m.get("freshness") == "recent" for m in matches):
            score += 0.1

        return min(score, 1.0), matches

    @staticmethod
    def _build_finn_match(
        w: "WantedListing",
        match_type: str,
        match_value: str,
        now: datetime,
    ) -> dict:
        """Build a match dict for one wanted listing."""
        # Freshness bucket
        days_since = (
            (now - w.last_seen_at).days if w.last_seen_at else 999
        )
        if days_since <= 7:
            freshness = "recent"
        elif days_since <= 30:
            freshness = "moderate"
        else:
            freshness = "stale"

        return {
            "finn_id": w.finn_id,
            "title": w.title,
            "offered_price": w.offered_price,
            "match_type": match_type,
            "match_value": match_value,
            "url": w.url,
            "freshness": freshness,
            "days_since_seen": days_since,
        }

    @staticmethod
    def _infer_finn_category(title: str) -> Optional[str]:
        """Infer a Finn wanted-listing category from a lot title.

        Uses keyword matching against the standard Finn furniture categories.
        The title should already be lowercased.

        Returns:
            Category string or None if no category can be inferred.
        """
        # Order matters: check more specific terms before generic ones.
        # "cabinet" keywords map to two possible categories; we pick the
        # more popular one ("Hyller og kommoder") for sideboard/byrå and
        # "Garderobe og skap" for wardrobe/garderobe/skap.
        if any(kw in title for kw in ("sofa", "couch", "soffa", "lenestol")):
            return "Sofaer og lenestoler"
        if any(kw in title for kw in ("wardrobe", "garderobe")):
            return "Garderobe og skap"
        if any(kw in title for kw in ("cabinet", "skap", "sideboard", "byrå", "kommode")):
            return "Hyller og kommoder"
        if any(kw in title for kw in ("shelf", "hylle", "shelving", "bookcase", "reol")):
            return "Hyller og kommoder"
        if any(kw in title for kw in ("lamp", "lampe", "pendant", "light", "taklampe")):
            return "Belysning"
        if any(kw in title for kw in ("chair", "stol", "chairs", "table", "bord", "desk")):
            return "Bord og stoler"
        return None

    # ------------------------------------------------------------------
    # Sub-signal 2: Historical hammer data
    # ------------------------------------------------------------------

    def _historical_flow_signal(
        self,
        parsed: ParsedLotFields,
        db: Session,
    ) -> tuple[Optional[float], dict]:
        """Score based on historical auction outcomes for similar items.

        Returns:
            Tuple of (score 0-1 or None, details dict with all metrics)
        """
        designers = [d.lower() for d in _parse_json_list(parsed.raw_designer_mentions)]
        object_type = (parsed.category_raw or "").lower().strip() or None

        if not designers and not object_type:
            return None, {}

        # Build query: match on designer_name OR object_type (case-insensitive)
        query = db.query(HistoricalHammer)
        conditions = []
        for d in designers:
            # Handle variant spellings: "hans j wegner" matches
            # "Hans J. Wegner", "Hans Wegner", etc. via LIKE with wildcards
            # between name parts.
            parts = d.split()
            if len(parts) >= 2:
                pattern = "%".join(parts)  # "hans%j%wegner"
                conditions.append(
                    func.lower(HistoricalHammer.designer_name).like(f"%{pattern}%")
                )
            elif len(parts) == 1 and len(parts[0]) > 3:
                conditions.append(
                    func.lower(HistoricalHammer.designer_name).like(f"%{parts[0]}%")
                )
        if object_type and len(object_type) > 3:
            conditions.append(
                func.lower(HistoricalHammer.object_type).like(f"%{object_type}%")
            )

        if not conditions:
            return None, {}

        records = query.filter(or_(*conditions)).all()

        if len(records) < 5:
            return None, {"record_count": len(records), "reason": "insufficient_data"}

        # --- Sell-through rate ---
        total = len(records)
        sold = sum(1 for r in records if r.was_sold == 1)
        sell_through = sold / total

        # --- Hammer-to-estimate ratio ---
        ratios = [
            r.hammer_price / r.estimate_low
            for r in records
            if r.hammer_price and r.estimate_low and r.estimate_low > 0
        ]
        avg_hammer_ratio = sum(ratios) / len(ratios) if ratios else None

        # --- Bid intensity ---
        bid_counts = [r.bid_count for r in records if r.bid_count is not None]
        avg_bid_count = sum(bid_counts) / len(bid_counts) if bid_counts else None

        # --- Price trend (recent 6 months vs older) ---
        price_trend = None
        dated_records = [
            r for r in records if r.auction_end_date and r.hammer_price
        ]
        if len(dated_records) >= 6:
            cutoff = datetime.utcnow() - timedelta(days=180)
            recent = [r.hammer_price for r in dated_records if r.auction_end_date >= cutoff]
            older = [r.hammer_price for r in dated_records if r.auction_end_date < cutoff]
            if recent and older:
                recent_avg = sum(recent) / len(recent)
                older_avg = sum(older) / len(older)
                if older_avg > 0:
                    price_trend = (recent_avg - older_avg) / older_avg  # positive = rising

        # --- Score mapping ---
        score = 0.0

        # Sell-through component (max 0.3)
        if sell_through > 0.9:
            score += 0.3
        elif sell_through > 0.7:
            score += 0.2
        elif sell_through > 0.5:
            score += 0.1

        # Hammer-to-estimate ratio component (max 0.3)
        if avg_hammer_ratio is not None:
            if avg_hammer_ratio > 1.5:
                score += 0.3
            elif avg_hammer_ratio > 1.2:
                score += 0.2
            elif avg_hammer_ratio > 1.0:
                score += 0.1

        # Bid intensity component (max 0.2)
        if avg_bid_count is not None:
            if avg_bid_count > 10:
                score += 0.2
            elif avg_bid_count > 5:
                score += 0.1

        # Price trend bonus (max 0.2)
        if price_trend is not None and price_trend > 0:
            score += min(0.2, price_trend * 0.5)  # +10% trend -> +0.05, cap 0.2

        details = {
            "record_count": total,
            "sold_count": sold,
            "sell_through_rate": round(sell_through, 3),
            "avg_hammer_ratio": round(avg_hammer_ratio, 3) if avg_hammer_ratio else None,
            "avg_bid_count": round(avg_bid_count, 1) if avg_bid_count else None,
            "price_trend": round(price_trend, 3) if price_trend is not None else None,
            "designers_queried": designers,
            "object_type_queried": object_type,
        }

        return min(score, 1.0), details

    # ------------------------------------------------------------------
    # Sub-signal 3: Resale confidence — "how easy is this to sell in Norway?"
    # ------------------------------------------------------------------

    @staticmethod
    def _price_percentile(prices: list[float], target: float) -> float:
        """What fraction of market prices is the target below?

        Returns 1.0 when target is cheapest (below all prices),
        0.0 when target is most expensive (above all prices).
        """
        if not prices:
            return 0.5
        below = sum(1 for p in prices if p > target)
        return below / len(prices)

    def _resale_confidence_signal(
        self,
        parsed: ParsedLotFields,
        db: Session,
    ) -> tuple[Optional[float], dict]:
        """Score how easy it would be to resell this item in Norway.

        Six components (max 1.0 total):
        1. Market exists        — binary gate
        2. Price certainty      — max 0.25
        3. Pricing advantage    — max 0.25
        4. Buyer pool depth     — max 0.20
        5. Listing velocity     — max 0.15
        6. Historical track     — max 0.15

        Uses a three-tier matching strategy inherited from the old supply
        signal: designer → brand → general benchmark.

        Returns:
            Tuple of (score 0-1 or None, details dict)
        """
        designers = [d.lower() for d in _parse_json_list(parsed.raw_designer_mentions)]
        match_type = "designer"

        # --- Tier 1: Find market data for this lot's designer(s) ---
        market_rows: list[FinnMarketData] = []
        for d in designers:
            rows = (
                db.query(FinnMarketData)
                .filter(
                    FinnMarketData.query_type == "designer",
                    func.lower(FinnMarketData.query_value).like(f"%{d}%"),
                )
                .order_by(FinnMarketData.scraped_at.desc())
                .all()
            )
            market_rows.extend(rows)

        # --- Tier 2: If no designer match, try brand matching from lot title ---
        if not market_rows:
            lot_title_lower = (parsed.title or "").lower()
            if lot_title_lower:
                brand_rows = db.query(FinnMarketData).filter(
                    FinnMarketData.query_type == "brand",
                ).all()
                for brand_row in brand_rows:
                    brand_name = brand_row.query_value.lower()
                    if brand_name in lot_title_lower:
                        market_rows.append(brand_row)
                if market_rows:
                    match_type = "brand"

        # --- Tier 3: General market benchmark across all brands ---
        if not market_rows:
            all_brands = db.query(FinnMarketData).filter(
                FinnMarketData.query_type == "brand",
                FinnMarketData.median_price_nok.isnot(None),
            ).all()
            if all_brands:
                median_prices = [b.median_price_nok for b in all_brands if b.median_price_nok]
                if median_prices:
                    general_median = statistics.median(median_prices)
                    general_count = sum(b.listing_count or 0 for b in all_brands)
                    score = 0.0
                    details: dict[str, Any] = {
                        "match_type": "general_benchmark",
                        "general_median_nok": general_median,
                        "brand_count": len(median_prices),
                        "total_listing_count": general_count,
                        "components": {},
                    }
                    # Only give market depth points, no margin points
                    if general_count >= 20:
                        score += 0.1
                    elif general_count >= 5:
                        score += 0.05
                    return min(score, 1.0), details

            return None, {}

        # ================================================================
        # Gate: Market exists — we have designer or brand matches
        # ================================================================

        # Use the best (most listings) market data row
        best = max(market_rows, key=lambda r: (r.listing_count or 0))

        # --- Parse price_samples ---
        samples = best.price_samples
        if isinstance(samples, str):
            try:
                samples = json.loads(samples)
            except (json.JSONDecodeError, TypeError):
                samples = []
        if not samples or not isinstance(samples, list):
            samples = []
        prices = [p for p in samples if isinstance(p, (int, float)) and p > 0]

        # Landed cost for this lot (SEK ≈ NOK, plus buyer premium)
        lot_cost_sek = parsed.estimate_low or parsed.current_bid or 0
        landed_cost = lot_cost_sek * (1.0 + self.buyer_premium_rate) if lot_cost_sek > 0 else 0.0

        # ================================================================
        # Component 1: Price certainty (max 0.25)
        # ================================================================
        cv = None
        comp_price_certainty = 0.0
        if len(prices) >= 2:
            mean_price = statistics.mean(prices)
            if mean_price > 0:
                std_dev = statistics.stdev(prices)
                cv = std_dev / mean_price
                if cv < 0.3:
                    comp_price_certainty = 0.25
                elif cv < 0.5:
                    comp_price_certainty = 0.15
                elif cv < 0.8:
                    comp_price_certainty = 0.05
                # cv >= 0.8 → 0.0

        # ================================================================
        # Component 2: Pricing advantage (max 0.25)
        # ================================================================
        percentile = None
        comp_pricing_advantage = 0.0
        if prices and landed_cost > 0:
            percentile = self._price_percentile(prices, landed_cost)
            if percentile >= 0.9:  # below P10 — massive undercut
                comp_pricing_advantage = 0.25
            elif percentile >= 0.75:  # below P25
                comp_pricing_advantage = 0.20
            elif percentile >= 0.5:  # below P50
                comp_pricing_advantage = 0.10
            # above P50 → 0.0

        # ================================================================
        # Component 3: Buyer pool depth (max 0.20)
        # ================================================================
        search_terms = designers if match_type == "designer" else [best.query_value.lower()]
        wanted_count = 0
        for term in search_terms:
            wanted_count += (
                db.query(WantedListing)
                .filter(
                    WantedListing.status == "active",
                    func.lower(WantedListing.title).like(f"%{term}%"),
                )
                .count()
            )

        listing_count = best.listing_count or 0
        total_pool = wanted_count + listing_count
        comp_buyer_pool = 0.0
        if total_pool >= 20:
            comp_buyer_pool = 0.15
        elif total_pool >= 5:
            comp_buyer_pool = 0.10
        elif total_pool >= 1:
            comp_buyer_pool = 0.05
        # Bonus for active wanted demand
        if wanted_count > 0:
            comp_buyer_pool = min(comp_buyer_pool + 0.05, 0.20)

        # ================================================================
        # Component 4: Listing velocity / churn (max 0.15)
        # ================================================================
        churn_rate = None
        comp_churn = 0.0
        try:
            forsale_query = db.query(FinnForSaleListing)
            forsale_conditions = []
            for term in search_terms:
                forsale_conditions.append(
                    func.lower(FinnForSaleListing.search_query).like(f"%{term}%")
                )
            if forsale_conditions:
                forsale_rows = forsale_query.filter(or_(*forsale_conditions)).all()
                if forsale_rows:
                    active_count = sum(1 for r in forsale_rows if r.status == "active")
                    disappeared_count = sum(1 for r in forsale_rows if r.status == "disappeared")
                    total_forsale = active_count + disappeared_count
                    if total_forsale > 0:
                        churn_rate = disappeared_count / total_forsale
                        if churn_rate > 0.3:
                            comp_churn = 0.15
                        elif churn_rate > 0.15:
                            comp_churn = 0.10
                        elif churn_rate > 0.05:
                            comp_churn = 0.05
        except Exception:
            # Table might not exist yet on first run — skip gracefully
            pass

        # ================================================================
        # Component 5: Historical track record (max 0.15)
        # ================================================================
        comp_track_record = 0.0
        hist_conditions = []
        for d in designers:
            parts = d.split()
            if len(parts) >= 2:
                pattern = "%".join(parts)
                hist_conditions.append(
                    func.lower(HistoricalHammer.designer_name).like(f"%{pattern}%")
                )
            elif len(parts) == 1 and len(parts[0]) > 3:
                hist_conditions.append(
                    func.lower(HistoricalHammer.designer_name).like(f"%{parts[0]}%")
                )
        if hist_conditions:
            hist_records = db.query(HistoricalHammer).filter(or_(*hist_conditions)).all()
            if len(hist_records) >= 5:
                total_hist = len(hist_records)
                sold_hist = sum(1 for r in hist_records if r.was_sold == 1)
                sell_through_rate = sold_hist / total_hist
                if sell_through_rate > 0.9:
                    comp_track_record = 0.15
                elif sell_through_rate > 0.7:
                    comp_track_record = 0.10

        # ================================================================
        # Combine components
        # ================================================================
        score = (
            comp_price_certainty
            + comp_pricing_advantage
            + comp_buyer_pool
            + comp_churn
            + comp_track_record
        )

        details: dict[str, Any] = {
            "match_type": match_type,
            "designer": best.query_value,
            "listing_count": listing_count,
            "median_price_nok": best.median_price_nok,
            "price_certainty_cv": round(cv, 3) if cv is not None else None,
            "pricing_advantage_percentile": round(percentile, 3) if percentile is not None else None,
            "landed_cost_nok": round(landed_cost, 0) if landed_cost > 0 else None,
            "churn_rate": round(churn_rate, 3) if churn_rate is not None else None,
            "buyer_pool": {"wanted": wanted_count, "for_sale": listing_count},
            "components": {
                "price_certainty": comp_price_certainty,
                "pricing_advantage": comp_pricing_advantage,
                "buyer_pool": comp_buyer_pool,
                "churn": comp_churn,
                "track_record": comp_track_record,
            },
        }

        return min(score, 1.0), details

    def _compute_overall_watch_score(
        self,
        arbitrage_score: Optional[float],
        taste_score: Optional[float],
        wildcard_score: Optional[float],
        urgency_score: Optional[float],
        demand_score: Optional[float] = None,
    ) -> Optional[float]:
        """Compute overall watch/interest score.

        Args:
            arbitrage_score: Arbitrage score
            taste_score: Taste score
            wildcard_score: Wildcard score
            urgency_score: Urgency score

        Returns:
            Combined score 0-1 or None
        """
        scores = []

        if arbitrage_score is not None:
            scores.append(arbitrage_score * self.weights.get("arbitrage", 0.3))
        if taste_score is not None:
            scores.append(taste_score * self.weights.get("taste", 0.4))
        if wildcard_score is not None:
            scores.append(wildcard_score * self.weights.get("wildcard", 0.2))
        if urgency_score is not None:
            scores.append(urgency_score * self.weights.get("urgency", 0.1))
        if demand_score is not None and demand_score > 0:
            scores.append(demand_score * self.weights.get("demand", 0.15))

        if not scores:
            return None

        return sum(scores) / len(scores)
