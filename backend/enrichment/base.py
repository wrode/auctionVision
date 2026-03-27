"""Base enrichment agent class."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.models import EnrichmentRun, EnrichmentOutput

logger = logging.getLogger(__name__)


class EnrichmentAgent(ABC):
    """Abstract base enrichment agent."""

    def __init__(self, agent_name: str, agent_version: str, model_name: Optional[str] = None):
        """Initialize enrichment agent.

        Args:
            agent_name: Name of the agent (e.g., "attribution", "arbitrage")
            agent_version: Version identifier
            model_name: Optional model name (e.g., "claude-3-5-sonnet")
        """
        self.agent_name = agent_name
        self.agent_version = agent_version
        self.model_name = model_name

    @abstractmethod
    async def run(
        self,
        lot_id: int,
        input_data: dict[str, Any],
        db: Session,
    ) -> dict[str, Any]:
        """Run enrichment on a lot.

        Args:
            lot_id: ID of the lot to enrich
            input_data: Input data for enrichment
            db: Database session

        Returns:
            Enrichment output as dictionary
        """
        pass

    async def execute(
        self,
        lot_id: int,
        input_data: dict[str, Any],
        db: Session,
        input_hash: Optional[str] = None,
        prompt_version: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Execute enrichment with database tracking.

        Args:
            lot_id: ID of the lot
            input_data: Input data
            db: Database session
            input_hash: Hash of input data
            prompt_version: Version of the prompt used

        Returns:
            Enrichment output or None if failed
        """
        # Create enrichment run record
        run = EnrichmentRun(
            lot_id=lot_id,
            agent_name=self.agent_name,
            agent_version=self.agent_version,
            model_name=self.model_name,
            prompt_version=prompt_version,
            input_hash=input_hash,
            started_at=datetime.utcnow(),
        )

        try:
            logger.info(f"Starting enrichment {self.agent_name} for lot {lot_id}")

            # Run the enrichment
            output = await self.run(lot_id, input_data, db)

            # Mark as successful
            run.completed_at = datetime.utcnow()
            run.success = 1

            # Store output
            enrichment_output = EnrichmentOutput(
                enrichment_run_id=run.id,
                lot_id=lot_id,
                output_json=output,
            )

            db.add(run)
            db.add(enrichment_output)
            db.commit()

            logger.info(f"Completed enrichment {self.agent_name} for lot {lot_id}")
            return output

        except Exception as e:
            logger.error(f"Error running enrichment {self.agent_name} for lot {lot_id}: {e}")
            run.completed_at = datetime.utcnow()
            run.success = 0
            run.error_message = str(e)
            db.add(run)
            db.commit()
            return None
