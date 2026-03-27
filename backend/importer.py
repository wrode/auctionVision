"""Importer for Claude-produced enrichment and comparable data."""

import json
import logging
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.models import EnrichmentRun, EnrichmentOutput, Comparable, Entity, Lot

logger = logging.getLogger(__name__)


class EnrichmentImporter:
    """Imports enrichment data from JSON files."""

    def __init__(self, db: Session):
        """Initialize importer.

        Args:
            db: Database session
        """
        self.db = db

    def import_enrichment_json(
        self,
        lot_id: int,
        agent_name: str,
        json_path: str | Path,
        agent_version: str = "claude_v1",
        model_name: str = "claude-3-5-sonnet-20241022",
    ) -> bool:
        """Import enrichment output from JSON file.

        Args:
            lot_id: ID of the lot
            agent_name: Name of the enrichment agent
            json_path: Path to JSON file with enrichment output
            agent_version: Version of the agent
            model_name: Name of the model used

        Returns:
            True if successful, False otherwise
        """
        json_path = Path(json_path)

        try:
            # Verify lot exists
            lot = self.db.query(Lot).filter(Lot.id == lot_id).first()
            if not lot:
                logger.error(f"Lot {lot_id} not found")
                return False

            # Read JSON file
            if not json_path.exists():
                logger.error(f"JSON file not found: {json_path}")
                return False

            with open(json_path, "r") as f:
                output_json = json.load(f)

            logger.info(f"Importing enrichment from {json_path}")

            # Create enrichment run
            run = EnrichmentRun(
                lot_id=lot_id,
                agent_name=agent_name,
                agent_version=agent_version,
                model_name=model_name,
                success=1,
            )
            self.db.add(run)
            self.db.flush()  # Get the run ID

            # Create enrichment output
            enrichment_output = EnrichmentOutput(
                enrichment_run_id=run.id,
                lot_id=lot_id,
                output_json=output_json,
            )
            self.db.add(enrichment_output)
            self.db.commit()

            logger.info(f"Imported enrichment for lot {lot_id} from agent {agent_name}")
            return True

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {json_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error importing enrichment for lot {lot_id}: {e}")
            self.db.rollback()
            return False

    def import_enrichments_batch(
        self,
        batch_json_path: str | Path,
        agent_name: str,
        agent_version: str = "claude_v1",
    ) -> int:
        """Import batch of enrichments from JSON file.

        The JSON file should contain:
        [
            {
                "lot_id": 123,
                "output": { ... enrichment output ... }
            },
            ...
        ]

        Args:
            batch_json_path: Path to batch JSON file
            agent_name: Name of the agent
            agent_version: Version of the agent

        Returns:
            Number of successfully imported enrichments
        """
        batch_json_path = Path(batch_json_path)
        count = 0

        try:
            with open(batch_json_path, "r") as f:
                batch = json.load(f)

            for item in batch:
                lot_id = item.get("lot_id")
                output_json = item.get("output")

                if not lot_id or not output_json:
                    logger.warning(f"Invalid batch item: {item}")
                    continue

                # Create enrichment run
                lot = self.db.query(Lot).filter(Lot.id == lot_id).first()
                if not lot:
                    logger.warning(f"Lot {lot_id} not found, skipping")
                    continue

                run = EnrichmentRun(
                    lot_id=lot_id,
                    agent_name=agent_name,
                    agent_version=agent_version,
                    success=1,
                )
                self.db.add(run)
                self.db.flush()

                enrichment_output = EnrichmentOutput(
                    enrichment_run_id=run.id,
                    lot_id=lot_id,
                    output_json=output_json,
                )
                self.db.add(enrichment_output)
                count += 1

            self.db.commit()
            logger.info(f"Imported {count} enrichments from {batch_json_path}")
            return count

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {batch_json_path}: {e}")
            return 0
        except Exception as e:
            logger.error(f"Error importing batch enrichments: {e}")
            self.db.rollback()
            return 0


class ComparablesImporter:
    """Imports comparable sales data from JSON files."""

    def __init__(self, db: Session):
        """Initialize importer.

        Args:
            db: Database session
        """
        self.db = db

    def import_comparables_json(self, json_path: str | Path) -> int:
        """Import comparable sales from JSON file.

        The JSON file should contain:
        [
            {
                "title": "Designer Chair",
                "object_type": "chair",
                "sold_price": 450,
                "currency": "SEK",
                "sold_at": "2024-03-15T10:30:00Z",
                "source_name": "auctionet",
                "external_ref": "lot-12345",
                "material_tags": ["wood", "leather"],
                "country": "Sweden",
                "confidence": 0.85
            },
            ...
        ]

        Args:
            json_path: Path to JSON file

        Returns:
            Number of imported comparables
        """
        json_path = Path(json_path)
        count = 0

        try:
            with open(json_path, "r") as f:
                comparables_list = json.load(f)

            for comp_data in comparables_list:
                comparable = Comparable(
                    source_name=comp_data.get("source_name"),
                    external_ref=comp_data.get("external_ref"),
                    title=comp_data.get("title"),
                    object_type=comp_data.get("object_type"),
                    material_tags=comp_data.get("material_tags"),
                    sold_price=comp_data.get("sold_price"),
                    currency=comp_data.get("currency"),
                    sold_at=comp_data.get("sold_at"),
                    country=comp_data.get("country"),
                    confidence=comp_data.get("confidence", 0.5),
                    raw_payload=comp_data,
                )

                # Link to entity if designer is mentioned
                designer_name = comp_data.get("designer")
                if designer_name:
                    entity = self.db.query(Entity).filter(
                        Entity.canonical_name.ilike(designer_name)
                    ).first()
                    if entity:
                        comparable.entity_id = entity.id

                self.db.add(comparable)
                count += 1

            self.db.commit()
            logger.info(f"Imported {count} comparables from {json_path}")
            return count

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {json_path}: {e}")
            return 0
        except Exception as e:
            logger.error(f"Error importing comparables: {e}")
            self.db.rollback()
            return 0

    def upsert_comparable(
        self,
        source_name: str,
        external_ref: str,
        comparable_data: dict[str, Any],
    ) -> bool:
        """Insert or update a single comparable.

        Args:
            source_name: Source of the comparable
            external_ref: External reference ID
            comparable_data: Comparable data

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if already exists
            existing = self.db.query(Comparable).filter(
                Comparable.source_name == source_name,
                Comparable.external_ref == external_ref,
            ).first()

            if existing:
                # Update existing
                existing.title = comparable_data.get("title")
                existing.object_type = comparable_data.get("object_type")
                existing.sold_price = comparable_data.get("sold_price")
                existing.currency = comparable_data.get("currency")
                existing.sold_at = comparable_data.get("sold_at")
                existing.confidence = comparable_data.get("confidence", 0.5)
                existing.raw_payload = comparable_data
            else:
                # Create new
                comparable = Comparable(
                    source_name=source_name,
                    external_ref=external_ref,
                    title=comparable_data.get("title"),
                    object_type=comparable_data.get("object_type"),
                    sold_price=comparable_data.get("sold_price"),
                    currency=comparable_data.get("currency"),
                    sold_at=comparable_data.get("sold_at"),
                    country=comparable_data.get("country"),
                    confidence=comparable_data.get("confidence", 0.5),
                    raw_payload=comparable_data,
                )
                self.db.add(comparable)

            self.db.commit()
            return True

        except Exception as e:
            logger.error(f"Error upserting comparable: {e}")
            self.db.rollback()
            return False
