"""Scoring engine for lot evaluation."""

import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.config import load_yaml_config
from backend.models import Lot, LotScores, ParsedLotFields, EnrichmentOutput

logger = logging.getLogger(__name__)


class ScoringEngine:
    """Engine for computing lot scores."""

    def __init__(self):
        """Initialize scoring engine."""
        # Load scoring weights from config
        self.config = load_yaml_config("scoring.yaml")
        self.version = self.config.get("version", "v1")
        self.weights = self.config.get("weights", {})

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
            # Get parsed fields
            parsed = db.query(ParsedLotFields).filter(
                ParsedLotFields.lot_id == lot_id
            ).order_by(ParsedLotFields.created_at.desc()).first()

            # Get enrichment outputs
            arbitrage_output = self._get_enrichment_output(lot_id, "arbitrage", db)
            taste_output = self._get_enrichment_output(lot_id, "taste", db)
            wildcard_output = self._get_enrichment_output(lot_id, "wildcard", db)

            # Compute scores
            arbitrage_score = self._compute_arbitrage_score(arbitrage_output)
            norway_gap_score = self._compute_norway_gap_score(arbitrage_output)
            taste_score = self._compute_taste_score(taste_output)
            wildcard_score = self._compute_wildcard_score(wildcard_output)
            urgency_score = self._compute_urgency_score(parsed)
            overall_watch_score = self._compute_overall_watch_score(
                arbitrage_score, taste_score, wildcard_score, urgency_score
            )

            # Create or update scores record
            scores = db.query(LotScores).filter(LotScores.lot_id == lot_id).first()
            if not scores:
                scores = LotScores(lot_id=lot_id)

            scores.scoring_version = self.version
            scores.arbitrage_score = arbitrage_score
            scores.norway_gap_score = norway_gap_score
            scores.taste_score = taste_score
            scores.wildcard_score = wildcard_score
            scores.urgency_score = urgency_score
            scores.overall_watch_score = overall_watch_score
            scores.explanation_json = {
                "arbitrage_output": arbitrage_output,
                "taste_output": taste_output,
                "wildcard_output": wildcard_output,
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

    def _compute_norway_gap_score(self, arbitrage_output: Optional[dict]) -> Optional[float]:
        """Compute Norway gap score.

        Args:
            arbitrage_output: Arbitrage enrichment output

        Returns:
            Score 0-1 or None
        """
        if not arbitrage_output:
            return None

        return arbitrage_output.get("arbitrage_score")  # Same as arbitrage for now

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

    def _compute_overall_watch_score(
        self,
        arbitrage_score: Optional[float],
        taste_score: Optional[float],
        wildcard_score: Optional[float],
        urgency_score: Optional[float],
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

        if not scores:
            return None

        return sum(scores) / len(scores)
