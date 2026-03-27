"""Abstract base parser class."""

from abc import ABC, abstractmethod
from typing import Any, Optional


class ParsedFields:
    """Data class for parsed lot fields."""

    def __init__(
        self,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        description: Optional[str] = None,
        category_raw: Optional[str] = None,
        condition_text: Optional[str] = None,
        dimensions_text: Optional[str] = None,
        current_bid: Optional[float] = None,
        estimate_low: Optional[float] = None,
        estimate_high: Optional[float] = None,
        currency: Optional[str] = None,
        auction_end_time: Optional[Any] = None,
        time_left_text: Optional[str] = None,
        provenance_text: Optional[str] = None,
        seller_location: Optional[str] = None,
        auction_house_name: Optional[str] = None,
        raw_designer_mentions: Optional[list[str]] = None,
        raw_material_mentions: Optional[list[str]] = None,
        image_urls: Optional[list[str]] = None,
        parse_confidence: float = 0.5,
    ):
        """Initialize parsed fields."""
        self.title = title
        self.subtitle = subtitle
        self.description = description
        self.category_raw = category_raw
        self.condition_text = condition_text
        self.dimensions_text = dimensions_text
        self.current_bid = current_bid
        self.estimate_low = estimate_low
        self.estimate_high = estimate_high
        self.currency = currency
        self.auction_end_time = auction_end_time
        self.time_left_text = time_left_text
        self.provenance_text = provenance_text
        self.seller_location = seller_location
        self.auction_house_name = auction_house_name
        self.raw_designer_mentions = raw_designer_mentions or []
        self.raw_material_mentions = raw_material_mentions or []
        self.image_urls = image_urls or []
        self.parse_confidence = parse_confidence

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "description": self.description,
            "category_raw": self.category_raw,
            "condition_text": self.condition_text,
            "dimensions_text": self.dimensions_text,
            "current_bid": self.current_bid,
            "estimate_low": self.estimate_low,
            "estimate_high": self.estimate_high,
            "currency": self.currency,
            "auction_end_time": self.auction_end_time,
            "time_left_text": self.time_left_text,
            "provenance_text": self.provenance_text,
            "seller_location": self.seller_location,
            "auction_house_name": self.auction_house_name,
            "raw_designer_mentions": self.raw_designer_mentions,
            "raw_material_mentions": self.raw_material_mentions,
            "image_urls": self.image_urls,
            "parse_confidence": self.parse_confidence,
        }


class BaseParser(ABC):
    """Abstract base parser for extracting data from auction HTML."""

    def __init__(self, parser_version: str):
        """Initialize parser.

        Args:
            parser_version: Version identifier for this parser
        """
        self.parser_version = parser_version

    @abstractmethod
    def parse(self, raw_html: str, lot_url: str) -> ParsedFields:
        """Parse raw HTML and extract lot fields.

        Args:
            raw_html: Raw HTML content
            lot_url: URL of the lot

        Returns:
            ParsedFields object with extracted data
        """
        pass
