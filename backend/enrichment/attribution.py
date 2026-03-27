"""Designer attribution enrichment agent."""

import logging
import re
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.enrichment.base import EnrichmentAgent

logger = logging.getLogger(__name__)


class AttributionAgent(EnrichmentAgent):
    """Agent for attributing designers and extracting object type/era/materials."""

    def __init__(self):
        """Initialize attribution agent."""
        super().__init__(
            agent_name="attribution",
            agent_version="v1",
            model_name=None,  # Rule-based, no LLM needed for v1
        )

    async def run(
        self,
        lot_id: int,
        input_data: dict[str, Any],
        db: Session,
    ) -> dict[str, Any]:
        """Run attribution analysis.

        Args:
            lot_id: ID of the lot
            input_data: Parsed fields and other metadata
            db: Database session

        Returns:
            Attribution output
        """
        logger.info(f"Running attribution analysis for lot {lot_id}")

        # Extract input data
        title = input_data.get("title", "")
        description = input_data.get("description", "")
        category_raw = input_data.get("category_raw", "")
        condition_text = input_data.get("condition_text", "")
        dimensions_text = input_data.get("dimensions_text", "")
        raw_designer_mentions = input_data.get("raw_designer_mentions", [])

        # Combine text for analysis
        full_text = f"{title} {description}".lower()

        # Extract designer candidate
        designer_candidate = self._match_designer(raw_designer_mentions, full_text)

        # Extract object type
        object_type = self._extract_object_type(category_raw, title, description)

        # Extract era
        era = self._extract_era(full_text, title)

        # Extract materials
        materials = self._extract_materials(full_text)

        # Build output
        output = {
            "designer_candidate": designer_candidate,
            "designer_confidence": 0.6 if designer_candidate else 0.0,
            "producer_candidate": None,
            "object_type": object_type,
            "era": era,
            "materials": materials,
            "attribution_flags": [],
            "risk_flags": self._identify_risk_flags(full_text),
        }

        logger.info(f"Attribution result: {output}")
        return output

    def _match_designer(self, mentions: list[str], text: str) -> Optional[str]:
        """Match designer from mentions against known designers.

        Args:
            mentions: Raw designer mentions
            text: Full text to search

        Returns:
            Matched designer name or None
        """
        # Common Scandinavian designers (seed list for MVP)
        known_designers = {
            "arne jacobsen": ["arne jacobsen", "jacobsen"],
            "hans wegner": ["hans wegner", "wegner"],
            "eames": ["eames"],
            "charles eames": ["charles eames"],
            "ray eames": ["ray eames"],
            "Le Corbusier": ["le corbusier", "corbusier"],
            "alvar aalto": ["alvar aalto", "aalto"],
            "finn juhl": ["finn juhl", "juhl"],
            "poul henningsen": ["poul henningsen", "henningsen", "ph"],
            "verner panton": ["verner panton", "panton"],
        }

        # Check mentions
        for mention in mentions:
            mention_lower = mention.lower()
            for designer, aliases in known_designers.items():
                if any(alias in mention_lower for alias in aliases):
                    return designer

        # Check text for designer references
        for designer, aliases in known_designers.items():
            for alias in aliases:
                if alias in text:
                    return designer

        return None

    def _extract_object_type(self, category: str, title: str, description: str) -> Optional[str]:
        """Extract object type from metadata.

        Args:
            category: Raw category
            title: Lot title
            description: Lot description

        Returns:
            Object type (e.g., "chair", "table", "lamp")
        """
        combined = f"{category} {title} {description}".lower()

        object_patterns = {
            "chair": [r"\bchair\b", r"\bchairs\b"],
            "table": [r"\btable\b", r"\btables\b"],
            "lamp": [r"\blamp\b", r"\blamps\b"],
            "sofa": [r"\bsofa\b", r"\bcouch\b"],
            "cabinet": [r"\bcabinet\b", r"\bcupboard\b"],
            "desk": [r"\bdesk\b"],
            "shelving": [r"\bshelf\b", r"\bshelves\b", r"\bshelving\b"],
        }

        for obj_type, patterns in object_patterns.items():
            for pattern in patterns:
                if re.search(pattern, combined, re.IGNORECASE):
                    return obj_type

        return None

    def _extract_era(self, text: str, title: str) -> Optional[str]:
        """Extract era/decade from text.

        Args:
            text: Full text to search
            title: Lot title

        Returns:
            Era label (e.g., "1950s", "mid-century")
        """
        combined = f"{text} {title}".lower()

        era_patterns = {
            "1900s": r"\b1900s\b",
            "1920s": r"\b1920s?\b",
            "1930s": r"\b1930s?\b",
            "1940s": r"\b1940s?\b",
            "1950s": r"\b1950s?\b",
            "1960s": r"\b1960s?\b",
            "1970s": r"\b1970s?\b",
            "mid-century": r"\bmid[\s-]century\b",
        }

        for era, pattern in era_patterns.items():
            if re.search(pattern, combined, re.IGNORECASE):
                return era

        return None

    def _extract_materials(self, text: str) -> list[str]:
        """Extract materials from text.

        Args:
            text: Text to search

        Returns:
            List of materials
        """
        materials = []

        material_patterns = {
            "wood": r"\b(wood|wooden|oak|teak|mahogany|walnut|rosewood|birch|beech)\b",
            "leather": r"\b(leather|suede)\b",
            "fabric": r"\b(fabric|upholstery|textile)\b",
            "plastic": r"\b(plastic|acrylic|resin|fiberglass)\b",
            "metal": r"\b(metal|steel|chrome|aluminum|brass|bronze|copper|iron)\b",
            "glass": r"\b(glass)\b",
            "marble": r"\b(marble)\b",
        }

        for material, pattern in material_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                materials.append(material)

        return materials

    def _identify_risk_flags(self, text: str) -> list[str]:
        """Identify potential risk flags.

        Args:
            text: Text to search

        Returns:
            List of risk flags
        """
        flags = []

        risk_patterns = {
            "reproduction": r"\b(reproduction|reissue|replica)\b",
            "damage": r"\b(damaged|broken|repair|crack|stain|wear)\b",
            "restoration": r"\b(restored|restoration)\b",
            "unlisted": r"\b(not listed|unlisted)\b",
        }

        for flag, pattern in risk_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                flags.append(flag)

        return flags
