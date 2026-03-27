"""Parser for Auctionet.com auction pages."""

import logging
import re
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup

from backend.parsers.base import BaseParser, ParsedFields

logger = logging.getLogger(__name__)


class AuctionetParser(BaseParser):
    """Parser for Auctionet.com auction lot pages."""

    def __init__(self):
        """Initialize Auctionet parser."""
        super().__init__(parser_version="auctionet_v1")

    def parse(self, raw_html: str, lot_url: str) -> ParsedFields:
        """Parse Auctionet lot page HTML.

        Args:
            raw_html: Raw HTML content
            lot_url: URL of the lot

        Returns:
            ParsedFields object with extracted data
        """
        try:
            soup = BeautifulSoup(raw_html, "lxml")

            # Extract title - typically in h1 or .lot-title
            title = self._extract_title(soup)

            # Extract description
            description = self._extract_description(soup)

            # Extract pricing information
            current_bid = self._extract_current_bid(soup)
            estimate_low, estimate_high = self._extract_estimates(soup)
            currency = self._extract_currency(soup)

            # Extract auction timeline
            auction_end_time = self._extract_auction_end_time(soup)
            time_left_text = self._extract_time_left(soup)

            # Extract condition and dimensions
            condition_text = self._extract_condition(soup)
            dimensions_text = self._extract_dimensions(soup)

            # Extract category
            category_raw = self._extract_category(soup)

            # Extract designer and material mentions
            full_text = title + " " + (description or "")
            raw_designer_mentions = self._extract_designer_mentions(full_text)
            raw_material_mentions = self._extract_material_mentions(full_text)

            # Extract images
            image_urls = self._extract_image_urls(soup)

            # Extract seller/location info
            seller_location = self._extract_seller_location(soup)

            return ParsedFields(
                title=title,
                subtitle=None,
                description=description,
                category_raw=category_raw,
                condition_text=condition_text,
                dimensions_text=dimensions_text,
                current_bid=current_bid,
                estimate_low=estimate_low,
                estimate_high=estimate_high,
                currency=currency,
                auction_end_time=auction_end_time,
                time_left_text=time_left_text,
                provenance_text=None,
                seller_location=seller_location,
                auction_house_name="Auctionet",
                raw_designer_mentions=raw_designer_mentions,
                raw_material_mentions=raw_material_mentions,
                image_urls=image_urls,
                parse_confidence=0.7,  # Auctionet layout is fairly consistent
            )

        except Exception as e:
            logger.error(f"Error parsing Auctionet page {lot_url}: {e}")
            return ParsedFields(parse_confidence=0.0)

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract lot title."""
        # Try common selectors
        title = soup.find("h1", class_="lot-title")
        if title:
            return title.get_text(strip=True)

        title = soup.find("h1")
        if title:
            return title.get_text(strip=True)

        # Fallback to og:title
        og_title = soup.find("meta", property="og:title")
        if og_title:
            return og_title.get("content")

        return None

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract lot description."""
        # Try common selectors
        desc = soup.find("div", class_="lot-description")
        if desc:
            return desc.get_text(strip=True)

        desc = soup.find("div", class_="description")
        if desc:
            return desc.get_text(strip=True)

        # Fallback to og:description
        og_desc = soup.find("meta", property="og:description")
        if og_desc:
            return og_desc.get("content")

        return None

    def _extract_current_bid(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract current bid amount."""
        # Look for current bid element
        bid_elem = soup.find("span", class_=re.compile(r"current.*bid|bid.*current"))
        if bid_elem:
            return self._extract_price(bid_elem.get_text())

        # Try generic price pattern
        for elem in soup.find_all(["span", "div"]):
            text = elem.get_text(strip=True)
            if "kr" in text.lower() or "sek" in text.lower():
                price = self._extract_price(text)
                if price:
                    return price

        return None

    def _extract_estimates(self, soup: BeautifulSoup) -> tuple[Optional[float], Optional[float]]:
        """Extract estimate range."""
        low, high = None, None

        # Look for estimate elements
        estimate_elem = soup.find("div", class_=re.compile(r"estimate"))
        if estimate_elem:
            text = estimate_elem.get_text()
            prices = re.findall(r"[\d\s]+\s*kr", text, re.IGNORECASE)
            if len(prices) >= 2:
                low = self._extract_price(prices[0])
                high = self._extract_price(prices[1])
            elif len(prices) == 1:
                low = self._extract_price(prices[0])

        return low, high

    def _extract_price(self, text: str) -> Optional[float]:
        """Extract numeric price from text."""
        # Remove currency symbols and whitespace
        text = re.sub(r"[^\d\s,.]", "", text)
        text = text.replace(",", ".").strip()

        # Try to parse as float
        try:
            return float(text)
        except ValueError:
            return None

    def _extract_currency(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract currency code."""
        text = soup.get_text()
        if "kr" in text.lower() or "sek" in text.lower():
            return "SEK"
        if "€" in text or "eur" in text.lower():
            return "EUR"
        return None

    def _extract_auction_end_time(self, soup: BeautifulSoup) -> Optional[datetime]:
        """Extract auction end time."""
        # Look for datetime attribute or specific text pattern
        for elem in soup.find_all(["span", "div"]):
            text = elem.get_text(strip=True)
            # Very simple pattern - real implementation would be more sophisticated
            if "ends" in text.lower() or "closes" in text.lower():
                # Would parse datetime here
                pass

        return None

    def _extract_time_left(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract time remaining text."""
        for elem in soup.find_all(["span", "div"]):
            text = elem.get_text(strip=True)
            if any(x in text.lower() for x in ["days", "hours", "minutes", "left", "remaining"]):
                return text

        return None

    def _extract_condition(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract condition information."""
        # Look for condition-specific elements
        cond = soup.find("div", class_=re.compile(r"condition"))
        if cond:
            return cond.get_text(strip=True)

        return None

    def _extract_dimensions(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract dimensions."""
        # Look for dimension patterns in text
        text = soup.get_text()
        matches = re.findall(r"(\d+\s*x\s*\d+\s*x?\s*\d*\s*(?:cm|mm|in|inches)?)", text)
        if matches:
            return matches[0]

        return None

    def _extract_category(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract category."""
        # Look for breadcrumb or category element
        breadcrumb = soup.find("div", class_=re.compile(r"breadcrumb|category"))
        if breadcrumb:
            return breadcrumb.get_text(strip=True)

        return "furniture"  # Default for initial MVP

    def _extract_designer_mentions(self, text: str) -> list[str]:
        """Extract potential designer names from text."""
        mentions = []

        # Common designer name patterns (simple regex - real impl would be more sophisticated)
        # Look for capitalized words that might be names
        potential_names = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", text)

        # Filter for name-like patterns (2-3 words, specific lengths)
        for name in potential_names:
            if 2 < len(name) < 30 and name.count(" ") <= 1:
                mentions.append(name)

        return list(set(mentions))[:5]  # Return top 5 unique mentions

    def _extract_material_mentions(self, text: str) -> list[str]:
        """Extract material mentions from text."""
        materials = []

        # Common materials
        material_patterns = [
            r"\b(wood|wooden|oak|teak|mahogany|walnut|rosewood)\b",
            r"\b(leather|suede|fabric|upholstery)\b",
            r"\b(plastic|acrylic|resin|fiberglass)\b",
            r"\b(metal|steel|chrome|aluminum|brass|bronze|copper)\b",
            r"\b(glass|marble|stone|ceramic)\b",
        ]

        for pattern in material_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            materials.extend(matches)

        return [m.lower() for m in list(set(materials))]

    def _extract_image_urls(self, soup: BeautifulSoup) -> list[str]:
        """Extract image URLs."""
        urls = []

        # Look for images in gallery
        for img in soup.find_all("img", class_=re.compile(r"lot|gallery|image")):
            src = img.get("src")
            if src and "data:" not in src:
                urls.append(src)

        # Also check for og:image
        og_image = soup.find("meta", property="og:image")
        if og_image:
            urls.insert(0, og_image.get("content"))

        # Return unique URLs
        return list(dict.fromkeys(urls))

    def _extract_seller_location(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract seller location."""
        # Look for seller or location information
        seller = soup.find("div", class_=re.compile(r"seller|location|address"))
        if seller:
            return seller.get_text(strip=True)

        return None
