"""Normalization layer for lot data."""

import logging
import re
from difflib import SequenceMatcher
from typing import Optional

from sqlalchemy.orm import Session

from backend.models import Entity

logger = logging.getLogger(__name__)


class Normalizer:
    """Normalizes lot data to canonical forms."""

    def __init__(self, db: Session):
        """Initialize normalizer.

        Args:
            db: Database session
        """
        self.db = db
        self.version = "v1"

    def normalize_designer(
        self,
        raw_mentions: list[str],
        fuzzy_threshold: float = 0.6,
    ) -> Optional[tuple[str, int, float]]:
        """Match designer mentions against known entities.

        Args:
            raw_mentions: List of raw designer mentions
            fuzzy_threshold: Fuzzy matching threshold (0-1)

        Returns:
            Tuple of (canonical_name, entity_id, confidence) or None
        """
        if not raw_mentions:
            return None

        # Query known designers
        known_designers = self.db.query(Entity).filter(
            Entity.entity_type == "designer"
        ).all()

        best_match = None
        best_score = 0.0

        for mention in raw_mentions:
            mention_lower = mention.lower()

            for designer in known_designers:
                # Check exact match
                if mention_lower == designer.canonical_name.lower():
                    return (designer.canonical_name, designer.id, 0.95)

                # Check aliases
                if designer.aliases:
                    for alias in designer.aliases:
                        if mention_lower == alias.lower():
                            return (designer.canonical_name, designer.id, 0.9)

                # Fuzzy match
                score = SequenceMatcher(None, mention_lower, designer.canonical_name.lower()).ratio()
                if score > fuzzy_threshold and score > best_score:
                    best_match = (designer.canonical_name, designer.id, score)
                    best_score = score

        return best_match

    def normalize_object_type(
        self,
        category_raw: Optional[str],
        title: Optional[str],
    ) -> Optional[str]:
        """Map raw category to canonical object type.

        Args:
            category_raw: Raw category string
            title: Lot title

        Returns:
            Canonical object type or None
        """
        combined = f"{category_raw or ''} {title or ''}".lower()

        # Mapping table
        object_type_mappings = {
            "chair": {
                "patterns": [r"\b(chair|chairs|stool|lounge chair)\b"],
                "canonical": "chair",
            },
            "table": {
                "patterns": [r"\b(table|tables|desk|coffee table)\b"],
                "canonical": "table",
            },
            "sofa": {
                "patterns": [r"\b(sofa|couch|settee|daybed)\b"],
                "canonical": "sofa",
            },
            "lamp": {
                "patterns": [r"\b(lamp|lamps|light|pendant|floor lamp)\b"],
                "canonical": "lamp",
            },
            "cabinet": {
                "patterns": [r"\b(cabinet|cupboard|shelving|shelves|shelf)\b"],
                "canonical": "cabinet",
            },
        }

        for type_key, mapping in object_type_mappings.items():
            for pattern in mapping["patterns"]:
                if re.search(pattern, combined, re.IGNORECASE):
                    return mapping["canonical"]

        return None

    def normalize_materials(
        self,
        raw_mentions: list[str],
    ) -> list[str]:
        """Map raw material mentions to canonical materials.

        Args:
            raw_mentions: List of raw material mentions

        Returns:
            List of canonical materials
        """
        # Canonical material list
        canonical_materials = [
            "wood",
            "leather",
            "fabric",
            "plastic",
            "metal",
            "glass",
            "marble",
            "ceramic",
            "rubber",
        ]

        # Mapping from variations to canonical
        material_mappings = {
            "wood": ["wood", "wooden", "oak", "teak", "mahogany", "walnut", "rosewood"],
            "leather": ["leather", "suede"],
            "fabric": ["fabric", "upholstery", "textile", "wool", "cotton"],
            "plastic": ["plastic", "acrylic", "resin", "fiberglass"],
            "metal": ["metal", "steel", "chrome", "aluminum", "brass", "bronze", "copper", "iron"],
            "glass": ["glass"],
            "marble": ["marble", "stone"],
            "ceramic": ["ceramic", "tile"],
            "rubber": ["rubber"],
        }

        normalized = []
        for mention in raw_mentions:
            mention_lower = mention.lower()
            for canonical, variations in material_mappings.items():
                if mention_lower in variations:
                    if canonical not in normalized:
                        normalized.append(canonical)
                    break

        return normalized

    def normalize_era(self, text_hints: Optional[str]) -> Optional[str]:
        """Extract and normalize era/decade.

        Args:
            text_hints: Text to search for era clues

        Returns:
            Era label (e.g., "1950s", "mid-century") or None
        """
        if not text_hints:
            return None

        text_lower = text_hints.lower()

        # Era patterns
        era_patterns = {
            "1900s": r"\b1900s?\b",
            "1920s": r"\b1920s?\b",
            "1930s": r"\b1930s?\b",
            "1940s": r"\b1940s?\b",
            "1950s": r"\b1950s?\b",
            "1960s": r"\b1960s?\b",
            "1970s": r"\b1970s?\b",
            "1980s": r"\b1980s?\b",
            "mid-century": r"\bmid[\s-]century\b",
            "contemporary": r"\bcontemporary\b",
            "modern": r"\bmodern\b",
        }

        for era, pattern in era_patterns.items():
            if re.search(pattern, text_lower, re.IGNORECASE):
                return era

        return None
