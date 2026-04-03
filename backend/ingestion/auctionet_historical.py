"""Auctionet ended-auction scraper for historical hammer prices.

Fetches ended auction results from Auctionet's search to build
a database of realized hammer prices. Used for BUY-SIDE prediction:
predicting what you'll have to pay, NOT what items are worth.

URL pattern: /sv/search/16-mobler?is=ended&q={query}&page={n}
Data: title, designer, object type, estimate, hammer price, auction house
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

BASE_URL = "https://auctionet.com"
ENDED_SEARCH_PATH = "/sv/search/16-mobler"

# Furniture keywords for filtering (Swedish)
FURNITURE_KEYWORDS = {
    "stol", "fåtölj", "soffa", "bord", "skåp", "hylla", "byrå",
    "sideboard", "skrivbord", "soffbord", "matbord", "pall",
    "bänk", "bokhylla", "hyllsystem", "fällbord", "nattduksbord",
    "chair", "armchair", "sofa", "table", "cabinet", "desk",
    "sideboard", "shelf", "shelving", "stool", "bench", "daybed",
}


async def fetch_ended_auctions(
    query: str = "",
    max_pages: int = 10,
    delay_seconds: float = 3.0,
) -> list[dict[str, Any]]:
    """Fetch ended auction results from Auctionet.

    Args:
        query: Search query (e.g., "Hans Wegner", "EA 208"). Empty = broad sweep.
        max_pages: Maximum pages to scrape.
        delay_seconds: Delay between page loads.

    Returns:
        List of item dicts with title, hammer_price, estimate, etc.
    """
    all_items = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for page_num in range(1, max_pages + 1):
            params = f"?is=ended&page={page_num}"
            if query:
                params += f"&q={query.replace(' ', '+')}"

            url = f"{BASE_URL}{ENDED_SEARCH_PATH}{params}"
            logger.info(f"Fetching ended auctions page {page_num}: {url}")

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(int(delay_seconds * 1000))

                # Extract items from the listing page using page.evaluate
                items = await page.evaluate("""
                    () => {
                        const results = [];
                        // Auctionet listing cards contain lot links and price info
                        const cards = document.querySelectorAll('a[href*="/sv/"]');
                        const seen = new Set();

                        cards.forEach(card => {
                            const href = card.getAttribute('href') || '';
                            // Match lot URLs: /sv/{id}-{slug}
                            const lotMatch = href.match(/\\/sv\\/(\\d+)-/);
                            if (!lotMatch) return;

                            const lotId = lotMatch[1];
                            if (seen.has(lotId)) return;
                            seen.add(lotId);

                            // Get the card's parent container text
                            const container = card.closest('article') || card.closest('[class*="item"]') || card.parentElement;
                            if (!container) return;

                            const text = container.innerText || '';
                            const title = card.querySelector('h2, h3, [class*="title"]');
                            const titleText = title ? title.innerText.trim() : '';

                            // Parse price: Auctionet ended cards show lines like:
                            //   "Klubbades 4 aug 2021"  (Swedish for "Hammered on")
                            //   "18 bud"                (bid count)
                            //   "1 250 EUR"             (hammer price)
                            let hammer = null;
                            let wasSold = false;
                            let bidCount = null;
                            let estimate = null;

                            // Look for "Klubbades" (sold) marker
                            if (text.match(/Klubbades/i)) {
                                wasSold = true;
                            }

                            // Extract price: "X EUR" pattern (the hammer price on ended lots)
                            const priceMatch = text.match(/(\\d[\\d\\s]*)\\s*EUR/);
                            if (priceMatch) {
                                const price = parseInt(priceMatch[1].replace(/\\s/g, ''));
                                if (price > 0) {
                                    hammer = price;
                                    if (!wasSold) wasSold = true;  // has a price = was sold
                                }
                            }

                            // Extract bid count: "X bud"
                            const bidMatch = text.match(/(\\d+)\\s*bud/i);
                            if (bidMatch) {
                                bidCount = parseInt(bidMatch[1]);
                            }

                            // Check if explicitly unsold
                            if (text.match(/(?:Ej\\s+såld|Unsold|Inte\\s+såld)/i)) {
                                wasSold = false;
                                hammer = null;
                            }

                            // Extract auction end date from "Klubbades DD mon YYYY"
                            let auctionEndDate = null;
                            const dateMatch = text.match(/Klubbades\\s+(\\d{1,2}\\s+\\w+\\s+\\d{4})/i);
                            if (dateMatch) {
                                auctionEndDate = dateMatch[1];
                            }

                            // Extract estimate range if shown
                            let estimateLow = null;
                            let estimateHigh = null;
                            const estMatch = text.match(/(?:Utrop|Estimate)[:\\s]*([\\d\\s]+)\\s*[-–]\\s*([\\d\\s]+)\\s*EUR/i);
                            if (estMatch) {
                                estimateLow = parseInt(estMatch[1].replace(/\\s/g, ''));
                                estimateHigh = parseInt(estMatch[2].replace(/\\s/g, ''));
                            }

                            results.push({
                                external_lot_id: lotId,
                                lot_url: href.startsWith('/') ? window.location.origin + href : href,
                                title: titleText || text.split('\\n')[0].substring(0, 200),
                                hammer_price: hammer,
                                estimate: estimate,
                                estimate_low: estimateLow,
                                estimate_high: estimateHigh,
                                was_sold: wasSold,
                                bid_count: bidCount,
                                auction_end_date: auctionEndDate,
                                raw_text: text.substring(0, 500),
                            });
                        });

                        return results;
                    }
                """)

                if not items:
                    logger.info(f"  No items on page {page_num}, stopping")
                    break

                all_items.extend(items)
                logger.info(f"  Page {page_num}: {len(items)} items (total: {len(all_items)})")

            except Exception as e:
                logger.error(f"  Error on page {page_num}: {e}")
                break

        await browser.close()

    return all_items


async def fetch_ended_lot_detail(lot_url: str) -> dict[str, Any]:
    """Fetch full detail of an ended lot for richer data extraction.

    Use this when listing page didn't provide enough data (e.g., missing
    designer info, description, materials).

    Args:
        lot_url: Full URL of the ended lot.

    Returns:
        Dict with title, description, hammer_price, designer, materials, etc.
    """
    from backend.parsers.auctionet import AuctionetParser

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(lot_url, wait_until="networkidle", timeout=30000)
            html = await page.content()
        finally:
            await browser.close()

    parser = AuctionetParser()
    parsed = parser.parse(html, lot_url)

    # Extract hammer price from ended lot page
    hammer_price = _extract_hammer_from_html(html)

    # Determine if sold
    was_sold = hammer_price is not None
    if not was_sold:
        # Check for unsold markers
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text()
        if re.search(r"(?:Ej såld|Unsold|Inte såld)", text, re.IGNORECASE):
            was_sold = False

    return {
        "title": parsed.title,
        "description": parsed.description,
        "category_raw": parsed.category_raw,
        "designer_mentions": parsed.raw_designer_mentions,
        "material_mentions": parsed.raw_material_mentions,
        "hammer_price": hammer_price,
        "estimate_low": parsed.estimate_low,
        "estimate_high": parsed.estimate_high,
        "currency": parsed.currency or "EUR",
        "auction_house_name": parsed.auction_house_name,
        "seller_location": parsed.seller_location,
        "auction_end_time": parsed.auction_end_time,
        "was_sold": was_sold,
    }


def _extract_hammer_from_html(html: str) -> Optional[float]:
    """Extract realized hammer price from ended lot HTML.

    Auctionet ended lots use various patterns:
    - "Klubbades" marker + price in EUR
    - "Slutpris: X EUR"
    - "Winning bid: X EUR"
    - "Highest bid: X EUR" (also present on ended lots)
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text()

    # Swedish: "Slutpris: X EUR"
    match = re.search(r"Slutpris[:\s]*(\d[\d\s]*)\s*EUR", text, re.IGNORECASE)
    if match:
        return float(match.group(1).replace(" ", ""))

    # English: "Sold for X EUR" or "Hammer price: X EUR"
    match = re.search(r"(?:Sold for|Hammer price)[:\s]*(\d[\d\s]*)\s*EUR", text, re.IGNORECASE)
    if match:
        return float(match.group(1).replace(" ", ""))

    # "Winning bid" / "Vinnande bud" / "Highest bid"
    match = re.search(r"(?:Winning bid|Vinnande bud|Highest bid)[:\s]*(\d[\d\s]*)\s*EUR", text, re.IGNORECASE)
    if match:
        return float(match.group(1).replace(" ", ""))

    return None


def _infer_designer(title: str, designer_mentions: list[str]) -> Optional[str]:
    """Infer primary designer name from title and mentions.

    Auctionet title patterns:
    - "CHARLES & RAY EAMES. Karmstol, ..." (uppercase name, period separator)
    - "HANS J WEGNER, sideboard, ..." (uppercase name, comma separator)
    - "SOFFA, 'GE-290', Hans J Wegner, Getama" (name embedded after model)
    - "STOL, 'CH-29', Hans J Wegner, Carl Hansen" (name after model)
    """
    if designer_mentions:
        return designer_mentions[0]

    # Known designer names to match in title (case-insensitive)
    known_designers = [
        "Hans J Wegner", "Hans Wegner", "Hans J. Wegner",
        "Arne Jacobsen", "Finn Juhl", "Borge Mogensen", "Børge Mogensen",
        "Poul Kjaerholm", "Poul Kjærholm",
        "Bruno Mathsson", "Verner Panton",
        "Niels Otto Møller", "Niels O. Møller", "N.O. Møller",
        "Ingmar Relling", "Kai Kristiansen",
        "Ole Wanscher", "Ib Kofod-Larsen", "Ib Kofod Larsen",
        "Alvar Aalto", "Ilmari Tapiovaara",
        "Charles & Ray Eames", "Charles Eames", "Ray Eames",
        "Poul Henningsen",
        "Kaare Klint", "Fritz Hansen", "Carl Hansen",
        "Nanna Ditzel", "Grete Jalk", "Peter Hvidt",
        "Arne Norell", "Yngve Ekström",
    ]
    title_lower = title.lower()
    for name in known_designers:
        if name.lower() in title_lower:
            return name

    # Pattern: "UPPERCASE NAME. rest" or "UPPERCASE NAME, rest"
    match = re.match(r"^([A-ZÅÄÖÆØÜ][A-ZÅÄÖÆØÜ&.\s]{3,40?})[.,]\s", title)
    if match:
        name = match.group(1).strip().rstrip(".")
        # Filter out furniture type words that aren't names
        non_names = {
            "SOFFA", "STOL", "BORD", "FÅTÖLJ", "HYLLA", "SIDEBOARD",
            "MATBORD", "BYRÅ", "PALL", "BÄNK", "SÄNG", "LAMPA",
            "FÅTÖLJER", "STOLAR", "SOFFOR", "SOFFBORD",
        }
        # Accept if it's not just a furniture word
        words = name.split()
        if words and words[0] not in non_names:
            return name.title()  # Convert to title case

    return None


def _infer_object_type(title: str, category_raw: Optional[str]) -> Optional[str]:
    """Infer object type from title and category."""
    text = f"{title} {category_raw or ''}".lower()
    mappings = [
        ("armchair", ["armchair", "fåtölj", "lenestol", "lounge chair", "easy chair"]),
        ("dining chair", ["dining chair", "matstol", "spisestol", "side chair"]),
        ("chair", ["chair", "stol"]),
        ("sofa", ["sofa", "soffa", "couch", "daybed"]),
        ("dining table", ["dining table", "matbord", "spisebord"]),
        ("coffee table", ["coffee table", "soffbord", "salongbord"]),
        ("table", ["table", "bord", "desk", "skrivbord"]),
        ("sideboard", ["sideboard", "skänk", "cabinet", "skåp", "byrå", "chest"]),
        ("shelving", ["shelf", "hylla", "hyllsystem", "shelving", "bookcase"]),
        ("stool", ["stool", "pall", "barstool"]),
        ("lamp", ["lamp", "lampa", "pendant", "taklampa", "golvlampa"]),
    ]
    for obj_type, keywords in mappings:
        if any(kw in text for kw in keywords):
            return obj_type
    return None


SWEDISH_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "maj": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}


def _parse_swedish_date(date_str: str) -> Optional[datetime]:
    """Parse '4 aug 2021' style Swedish dates."""
    if not date_str:
        return None
    try:
        parts = date_str.strip().split()
        if len(parts) == 3:
            day = int(parts[0])
            month = SWEDISH_MONTHS.get(parts[1].lower())
            year = int(parts[2])
            if month:
                return datetime(year, month, day)
    except (ValueError, IndexError):
        pass
    return None


def to_historical_records(items: list[dict]) -> list[dict]:
    """Convert scraped items to HistoricalHammer record format.

    Args:
        items: Raw scraped items from fetch_ended_auctions.

    Returns:
        List of dicts ready for DB import.
    """
    records = []
    for item in items:
        title = item.get("title", "")
        if not title:
            continue

        designer = _infer_designer(title, item.get("designer_mentions", []))
        object_type = _infer_object_type(title, item.get("category_raw"))

        records.append({
            "external_lot_id": item["external_lot_id"],
            "lot_url": item["lot_url"],
            "title": title[:500],
            "description": item.get("description"),
            "category_raw": item.get("category_raw"),
            "designer_name": designer,
            "object_type": object_type,
            "materials": item.get("material_mentions"),
            "hammer_price": item.get("hammer_price"),
            "estimate_low": item.get("estimate_low") or item.get("estimate"),
            "estimate_high": item.get("estimate_high") or item.get("estimate"),
            "currency": item.get("currency", "EUR"),
            "auction_house_name": item.get("auction_house_name"),
            "seller_location": item.get("seller_location"),
            "auction_end_date": _parse_swedish_date(item.get("auction_end_date")) or item.get("auction_end_time"),
            "bid_count": item.get("bid_count"),
            "was_sold": 1 if item.get("was_sold") else 0,
            "scraped_at": datetime.utcnow(),
        })

    return records


def import_to_db(records: list[dict], db) -> int:
    """Import historical hammer records to database with upsert logic.

    Args:
        records: List of record dicts from to_historical_records.
        db: SQLAlchemy session.

    Returns:
        Number of new records inserted.
    """
    from backend.models import HistoricalHammer

    # Deduplicate within batch (same lot can appear on multiple pages)
    seen = set()
    unique_records = []
    for rec in records:
        eid = rec["external_lot_id"]
        if eid not in seen:
            seen.add(eid)
            unique_records.append(rec)

    inserted = 0
    backfilled = 0
    for rec in unique_records:
        existing = db.query(HistoricalHammer).filter(
            HistoricalHammer.external_lot_id == rec["external_lot_id"]
        ).first()

        if existing:
            updated = False
            # Update hammer price if we have it and they don't
            if rec.get("hammer_price") and not existing.hammer_price:
                existing.hammer_price = rec["hammer_price"]
                existing.was_sold = rec["was_sold"]
                updated = True
            # Backfill auction_end_date if missing
            if rec.get("auction_end_date") and not existing.auction_end_date:
                existing.auction_end_date = rec["auction_end_date"]
                updated = True
            # Backfill bid_count if missing
            if rec.get("bid_count") is not None and existing.bid_count is None:
                existing.bid_count = rec["bid_count"]
                updated = True
            # Backfill estimates if missing
            if rec.get("estimate_low") and not existing.estimate_low:
                existing.estimate_low = rec["estimate_low"]
                updated = True
            if rec.get("estimate_high") and not existing.estimate_high:
                existing.estimate_high = rec["estimate_high"]
                updated = True
            if updated:
                existing.scraped_at = datetime.utcnow()
                backfilled += 1
            continue

        row = HistoricalHammer(**rec)
        db.add(row)
        inserted += 1

    db.commit()
    logger.info(f"Imported {inserted} new, backfilled {backfilled} existing ({len(unique_records) - inserted - backfilled} unchanged)")
    return inserted
