"""Parser for Auctionet.com auction pages."""

import html as htmlmod
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from bs4 import BeautifulSoup

from backend.parsers.base import BaseParser, ParsedFields

logger = logging.getLogger(__name__)


class AuctionetParser(BaseParser):
    """Parser for Auctionet.com auction lot pages."""

    def __init__(self):
        """Initialize Auctionet parser."""
        super().__init__(parser_version="auctionet_v2")

    def parse(self, raw_html: str, lot_url: str) -> ParsedFields:
        """Parse Auctionet lot page HTML.

        Args:
            raw_html: Raw HTML content
            lot_url: URL of the lot

        Returns:
            ParsedFields object with extracted data
        """
        try:
            soup = BeautifulSoup(raw_html, "html.parser")

            # Extract structured bid data from React props JSON
            item_json = self._extract_item_json(raw_html)

            # Extract title from <h1>
            title = self._extract_title(soup)

            # Extract subtitle from page <title> tag
            subtitle = self._extract_subtitle(soup)

            # Extract description from <h2>Description</h2> → next sibling
            description = self._extract_description(soup)

            # Extract dimensions from description text
            dimensions_text = self._extract_dimensions(description)

            # Extract condition from <h2>Condition</h2> → next sibling
            condition_text = self._extract_condition(soup)

            # Extract designer from <h2>Artist/designer</h2> → next sibling
            designer_raw = self._extract_designer_raw(soup)

            # Extract pricing from JSON first, fall back to HTML scraping
            current_bid = self._extract_current_bid_from_json(item_json) or self._extract_current_bid(soup)
            bid_count = self._extract_bid_count(item_json)
            hammer_price = self._extract_hammer_price(item_json)
            sold_at = self._extract_sold_at(item_json)
            estimate_low, estimate_high = self._extract_estimates_from_json(item_json) or self._extract_estimates(soup)
            currency = item_json.get("currency", "EUR") if item_json else "EUR"

            # Extract auction timeline
            auction_end_time = self._extract_auction_end_time_from_json(item_json) or self._extract_auction_end_time(soup)
            time_left_text = self._extract_time_left(soup)

            # Extract category from breadcrumbs or page title
            category_raw = self._extract_category(soup)

            # Extract designer and material mentions from title + description
            full_text = (title or "") + " " + (description or "") + " " + (designer_raw or "")
            raw_designer_mentions = self._extract_designer_mentions(full_text)
            raw_material_mentions = self._extract_material_mentions(description or "")

            # Extract images
            image_urls = self._extract_image_urls(soup)

            # Extract seller/location info
            seller_location = self._extract_seller_location(soup)
            auction_house_name = self._extract_auction_house(soup)

            # Higher confidence when we have the JSON blob
            confidence = 0.95 if item_json else 0.8

            return ParsedFields(
                title=title,
                subtitle=subtitle,
                description=description,
                category_raw=category_raw,
                condition_text=condition_text,
                dimensions_text=dimensions_text,
                current_bid=current_bid,
                bid_count=bid_count,
                hammer_price=hammer_price,
                sold_at=sold_at,
                estimate_low=estimate_low,
                estimate_high=estimate_high,
                currency=currency,
                auction_end_time=auction_end_time,
                time_left_text=time_left_text,
                provenance_text=None,
                seller_location=seller_location,
                auction_house_name=auction_house_name,
                raw_designer_mentions=raw_designer_mentions,
                raw_material_mentions=raw_material_mentions,
                image_urls=image_urls,
                parse_confidence=confidence,
            )

        except Exception as e:
            logger.error(f"Error parsing Auctionet page {lot_url}: {e}")
            return ParsedFields(parse_confidence=0.0)

    # ------------------------------------------------------------------
    # JSON-based extractors (from data-react-props on the bid component)
    # ------------------------------------------------------------------

    def _extract_item_json(self, raw_html: str) -> Optional[dict[str, Any]]:
        """Extract the structured item JSON from the React props attribute."""
        for match in re.finditer(r'data-react-props="([^"]{50,})"', raw_html):
            val = htmlmod.unescape(match.group(1))
            try:
                data = json.loads(val)
                if "item" in data:
                    return data["item"]
            except (json.JSONDecodeError, KeyError):
                continue
        return None

    def _extract_current_bid_from_json(self, item: Optional[dict]) -> Optional[float]:
        """Get leading bid amount from the JSON bids array.

        Bids are in reverse chronological order (newest/highest first).
        """
        if not item:
            return None
        bids = item.get("bids", [])
        if bids:
            return float(bids[0]["amount"])
        return None

    def _extract_bid_count(self, item: Optional[dict]) -> Optional[int]:
        """Get number of bids from the JSON bids array."""
        if not item:
            return None
        return len(item.get("bids", []))

    def _extract_hammer_price(self, item: Optional[dict]) -> Optional[float]:
        """Get final sold price. Only set when state is 'sold'.

        Bids are in reverse chronological order (newest/highest first).
        """
        if not item or item.get("state") != "sold":
            return None
        bids = item.get("bids", [])
        if bids:
            return float(bids[0]["amount"])
        return None

    def _extract_sold_at(self, item: Optional[dict]) -> Optional[datetime]:
        """Get sold timestamp from the last bid's time on sold lots."""
        if not item or item.get("state") not in ("sold", "unsold"):
            return None
        # Use ends_at as the sold/ended timestamp
        ends_at = item.get("ends_at")
        if ends_at:
            return datetime.fromtimestamp(ends_at, tz=timezone.utc)
        return None

    def _extract_estimates_from_json(self, item: Optional[dict]) -> Optional[tuple[Optional[float], Optional[float]]]:
        """Get estimate range from JSON."""
        if not item:
            return None
        estimate = item.get("estimate")
        upper = item.get("upper_estimate")
        if estimate is not None:
            return (float(estimate), float(upper) if upper else float(estimate))
        return None

    def _extract_auction_end_time_from_json(self, item: Optional[dict]) -> Optional[datetime]:
        """Get auction end time from JSON unix timestamp."""
        if not item:
            return None
        ends_at = item.get("ends_at")
        if ends_at:
            return datetime.fromtimestamp(ends_at, tz=timezone.utc)
        return None

    def _item_state(self, raw_html: str) -> Optional[str]:
        """Return the lot state: 'published', 'sold', or 'unsold'."""
        item = self._extract_item_json(raw_html)
        if item:
            return item.get("state")
        return None

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract lot title from <h1> tag."""
        title_elem = soup.find("h1")
        if title_elem:
            text = title_elem.get_text(strip=True)
            # Strip leading lot number if present (e.g., "5001970. BÖRGE MOGENSEN...")
            text = re.sub(r"^\d+\.\s*", "", text)
            return text if text else None
        return None

    def _extract_subtitle(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract subtitle from page <title> tag."""
        title_tag = soup.find("title")
        if title_tag:
            # Format is typically "TITLE. Category - Subcategory - Auctionet"
            # Extract the subcategory part
            text = title_tag.get_text(strip=True)
            # Split on " - Auctionet" and take the subcategory part
            if " - Auctionet" in text:
                parts = text.split(" - Auctionet")[0].split(" - ")
                if len(parts) >= 2:
                    return parts[-1]  # Return last category part
        return None

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract lot description from <h2>Description</h2> → next sibling."""
        # Find <h2> with text "Description"
        for h2 in soup.find_all("h2"):
            if h2.get_text(strip=True).lower() == "description":
                # Get the next sibling (usually a div or p)
                next_elem = h2.find_next_sibling()
                if next_elem:
                    return next_elem.get_text(strip=True)
        return None

    def _extract_current_bid(self, soup: BeautifulSoup) -> Optional[float]:
        """Extract current bid from the bid info panel."""
        bid_text = self._extract_bid_info_value(soup, "highest bid", "primary")
        if bid_text:
            if "no bids" in bid_text.lower():
                return None
            match = re.search(r"(\d[\d\s\xa0,.]*)\s*EUR", bid_text, re.IGNORECASE)
            if match:
                return self._extract_price(match.group(1).replace("\xa0", " "))

        text = soup.get_text(" ", strip=True)
        match = re.search(r"Highest bid:?\s*(\d[\d\s\xa0,.]*)\s*EUR", text, re.IGNORECASE)
        if match:
            return self._extract_price(match.group(1).replace("\xa0", " "))
        if re.search(r"Highest bid:?\s*No bids", text, re.IGNORECASE):
            return None
        return None

    def _extract_estimates(self, soup: BeautifulSoup) -> tuple[Optional[float], Optional[float]]:
        """Extract estimate from the bid info panel."""
        estimate_text = self._extract_bid_info_value(soup, "highest bid", "secondary")
        if estimate_text:
            match = re.search(r"Estimate:?\s*(\d[\d\s\xa0,.]*)\s*EUR", estimate_text, re.IGNORECASE)
            if match:
                price = self._extract_price(match.group(1).replace("\xa0", " "))
                return price, price

        text = soup.get_text(" ", strip=True)
        match = re.search(r"Estimate:?\s*(\d[\d\s\xa0,.]*)\s*EUR", text, re.IGNORECASE)
        if match:
            price = self._extract_price(match.group(1).replace("\xa0", " "))
            return price, price
        return None, None

    def _extract_bid_info_value(self, soup: BeautifulSoup, header_label: str, value_kind: str) -> Optional[str]:
        """Extract a value from Auctionet's bid-info columns."""
        value_class = {
            "primary": ".item-page__bid-info__primary-value",
            "secondary": ".item-page__bid-info__secondary-value",
        }.get(value_kind)
        if value_class is None:
            return None

        for column in soup.select(".item-page__bid-info__column"):
            header = column.select_one(".item-page__bid-info__header")
            if not header:
                continue
            header_text = header.get_text(" ", strip=True).lower()
            if not header_text.startswith(header_label.lower()):
                continue
            value = column.select_one(value_class)
            if value:
                return value.get_text(" ", strip=True)
        return None

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


    def _extract_auction_end_time(self, soup: BeautifulSoup) -> Optional[datetime]:
        """Extract auction end time from '3 Apr 2026 at 21:24 CEST' format."""
        text = soup.get_text()
        # Look for date pattern like "3 Apr 2026 at 21:24 CEST"
        match = re.search(
            r"(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})\s+at\s+(\d{1,2}):(\d{2})\s*([A-Z]{3,4})?",
            text
        )
        if match:
            day, month_str, year, hour, minute, tz = match.groups()
            try:
                # Parse the date
                date_str = f"{day} {month_str} {year} {hour}:{minute}"
                # Map month abbreviation to number
                months = {
                    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
                    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
                }
                month_num = months.get(month_str.lower())
                if month_num:
                    dt = datetime(int(year), month_num, int(day), int(hour), int(minute))
                    return dt
            except (ValueError, KeyError):
                pass
        return None

    def _extract_time_left(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract time remaining text like '7 days' or '21 hours'."""
        text = soup.get_text()
        # Look for patterns like "9 days", "7 days", "21 hours"
        match = re.search(r"(\d+\s+(?:days?|hours?|minutes?))", text, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def _extract_condition(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract condition from <h2>Condition</h2> → next sibling."""
        # Find <h2> with text "Condition"
        for h2 in soup.find_all("h2"):
            if h2.get_text(strip=True).lower() == "condition":
                # Get the next sibling (usually a p tag)
                next_elem = h2.find_next_sibling()
                if next_elem:
                    return next_elem.get_text(strip=True)
        return None

    def _extract_dimensions(self, text: Optional[str]) -> Optional[str]:
        """Extract dimensions from description text (e.g., 'Length 158, depth 81, height 76 cm')."""
        if not text:
            return None
        # Look for dimension patterns like "Length 158, depth 81, height 76 cm"
        # or "Height 68, seat height 46, width 52 cm"
        match = re.search(
            r"((?:Length|Height|Width|Depth|Seat height|Diameter).*?(?:cm|mm|inches?))",
            text,
            re.IGNORECASE
        )
        if match:
            return match.group(1)
        return None

    def _extract_category(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract category from page title (format: 'Title. MainCat - SubCat - Auctionet')."""
        title_tag = soup.find("title")
        if title_tag:
            text = title_tag.get_text(strip=True)
            if " - Auctionet" in text:
                before = text.split(" - Auctionet")[0]
                parts = before.split(" - ")
                if len(parts) >= 2:
                    # First part is "Lot Title. MainCategory", rest are subcategories
                    main_part = parts[0]
                    # Extract main category after last ". "
                    dot_idx = main_part.rfind(". ")
                    main_cat = main_part[dot_idx + 2:].strip() if dot_idx >= 0 else None
                    sub_cats = [p.strip() for p in parts[1:] if p.strip()]
                    cats = ([main_cat] if main_cat else []) + sub_cats
                    if cats:
                        return " > ".join(cats)
        return None

    def _extract_designer_mentions(self, text: str) -> list[str]:
        """Extract designer names from text (e.g., 'Poul Henningsen (1894–1967)')."""
        mentions = []

        # Look for pattern: "Name (YYYY–YYYY)" or "Name (YYYY-YYYY)"
        designer_pattern = r"\b([A-Z][a-zà-öø-ÿ]+(?:\s+[A-Z][a-zà-öø-ÿ]+)+)\s+\(\d{4}[–-]\d{4}\)"
        matches = re.findall(designer_pattern, text)
        mentions.extend(matches)

        return list(dict.fromkeys(mentions))[:10]

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
        """Extract the main gallery image URLs with 'large_' prefix."""
        urls = []

        for img in soup.select(".item-page__images img.test-item-image"):
            src = img.get("src")
            data_pin_media = img.get("data-pin-media")
            candidate = src or data_pin_media
            if not candidate or "item_" not in candidate or "data:" in candidate:
                continue
            large_src = (
                candidate
                .replace("/uploads/item_", "/thumbs/large_item_")
                .replace("medium_", "large_")
                .replace("thumb_", "large_")
                .replace("mini_", "large_")
            )
            urls.append(large_src)

        og_image = soup.find("meta", property="og:image")
        if og_image:
            content = og_image.get("content")
            if content:
                urls.insert(0, content.replace("medium_", "large_").replace("mini_", "large_"))

        return list(dict.fromkeys(urls))

    def _extract_seller_location(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract seller location from 'Item is located in X' in HTML."""
        # Search raw HTML to avoid get_text() bleeding adjacent elements together
        html_str = str(soup)
        match = re.search(r"Item is located in\s+([^<]+)", html_str, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    def _extract_auction_house(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract auction house name from logo alt text in header-and-logo section."""
        logo_div = soup.find(class_="header-and-logo__logo")
        if logo_div:
            img = logo_div.find("img")
            if img and img.get("alt"):
                return img["alt"].strip()
        # Fallback: look for company link in header area
        company_link = soup.find("a", href=re.compile(r"company_id="))
        if company_link:
            img = company_link.find("img")
            if img and img.get("alt"):
                return img["alt"].strip()
        return None

    def _extract_designer_raw(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract designer info from <h2>Artist/designer</h2> → next sibling."""
        # Find <h2> with text "Artist/designer"
        for h2 in soup.find_all("h2"):
            h2_text = h2.get_text(strip=True).lower()
            if "artist" in h2_text or "designer" in h2_text:
                # Get the next sibling (usually a p tag)
                next_elem = h2.find_next_sibling()
                if next_elem:
                    return next_elem.get_text(strip=True)
        return None
