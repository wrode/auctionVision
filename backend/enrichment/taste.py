"""Taste matching enrichment agent."""

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.enrichment.base import EnrichmentAgent

logger = logging.getLogger(__name__)


class TasteAgent(EnrichmentAgent):
    """Agent for taste-based lot matching and classification."""

    def __init__(self):
        """Initialize taste agent."""
        super().__init__(
            agent_name="taste",
            agent_version="v1",
            model_name=None,  # Rule-based implementation
        )

    async def run(
        self,
        lot_id: int,
        input_data: dict[str, Any],
        db: Session,
    ) -> dict[str, Any]:
        """Run taste analysis.

        Args:
            lot_id: ID of the lot
            input_data: Attribution data, user taste profile, etc
            db: Database session

        Returns:
            Taste output
        """
        logger.info(f"Running taste analysis for lot {lot_id}")

        # Extract input
        designer_candidate = input_data.get("designer_candidate")
        object_type = input_data.get("object_type")
        era = input_data.get("era")

        # Seed designers (define the "core" taste profile)
        seed_designers = {
            "arne jacobsen": "core",
            "hans wegner": "core",
            "finn juhl": "core",
            "alvar aalto": "adjacent",
            "eames": "adjacent",
        }

        # Determine taste mode and score
        taste_score = None
        mode = None

        if designer_candidate:
            designer_lower = designer_candidate.lower()
            if designer_lower in seed_designers:
                mode = seed_designers[designer_lower]
                taste_score = 0.9 if mode == "core" else 0.7

        # Build output
        output = {
            "taste_score": taste_score,
            "mode": mode or "exploratory",
            "similar_to": [],
            "adjacent_entities": [],
            "reasons": [
                f"Designer: {designer_candidate}" if designer_candidate else "No designer match",
                f"Object type: {object_type}" if object_type else "Unknown type",
                f"Era: {era}" if era else "Unknown era",
            ],
        }

        logger.info(f"Taste result: {output}")
        return output
