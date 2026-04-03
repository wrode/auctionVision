"""Blomqvist auction house scraper for Norwegian realized prices.

Fetches the "Tilslagslisten" (hammer price list) from blomqvist.no
for the "Moderne møbler og design" category.

URL pattern: /auksjoner/solgte-objekter?categories=SL&page={n}
Data: title, designer, object type, estimate, hammer price (tilslag)
"""

import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

# Furniture-related Norwegian terms
FURNITURE_KEYWORDS = {
    "stol", "sofa", "bord", "skap", "hylle", "skatoll", "benk", "krakk",
    "speil", "lenestol", "reol", "kommmode", "sidebord", "spisebord",
    "salongbord", "seksjon", "skjenk", "sybord", "skrivebord",
}
NON_FURNITURE = {
    "vase", "bolle", "skål", "fat", "glass", "servise", "kanne",
    "lysestaker", "figur", "relieff", "statuett", "sølv", "potteskjuler",
    "kandelaber", "mugge", "bøsser", "terrin", "ur", "bestikk",
    "kopp", "tallerken", "tekanne", "sukkerskål",
}

NOK_EUR = 0.085
BASE_URL = "https://www.blomqvist.no/auksjoner/solgte-objekter"


async def fetch_blomqvist_tilslag(
    categories: str = "SL",
    max_pages: int = 7,
) -> list[dict[str, Any]]:
    """Fetch realized prices from Blomqvist's tilslagsliste.

    Args:
        categories: Category code (SL = Moderne møbler og design)
        max_pages: Maximum pages to fetch

    Returns:
        List of item dicts with title, desc, estimate, hammer, etc.
    """
    all_items = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for page_num in range(1, max_pages + 1):
            url = f"{BASE_URL}?categories={categories}&page={page_num}"
            logger.info(f"Fetching Blomqvist page {page_num}: {url}")

            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(2000)

                # Extract items from .info elements
                items = await page.evaluate("""
                    () => {
                        const infos = document.querySelectorAll('.info');
                        const items = [];
                        infos.forEach(info => {
                            const card = info.parentElement;
                            if (!card) return;
                            const text = card.innerText.trim();
                            if (!text.includes('NOK')) return;
                            const lines = text.split('\\n').map(l => l.trim()).filter(l => l.length > 0);
                            let title = '', desc = '', estLow = null, estHigh = null, hammer = null, sold = false;
                            lines.forEach(line => {
                                const estMatch = line.match(/^([\\d.]+)\\s*-\\s*([\\d.]+)\\s*NOK$/);
                                const tilslagMatch = line.match(/^Tilslag\\s+([\\d.]+)\\s*NOK$/);
                                const singlePrice = line.match(/^([\\d.]+)\\s*NOK$/);
                                if (tilslagMatch) { hammer = parseInt(tilslagMatch[1].replace(/\\./g, '')); sold = true; }
                                else if (line === 'Usolgt') { sold = false; }
                                else if (estMatch) { estLow = parseInt(estMatch[1].replace(/\\./g, '')); estHigh = parseInt(estMatch[2].replace(/\\./g, '')); }
                                else if (singlePrice && !estLow) { estLow = parseInt(singlePrice[1].replace(/\\./g, '')); }
                                else if (!title && line.length > 2 && !line.match(/^\\d/)) { title = line; }
                                else if (title && !desc && line.length > 2 && !line.match(/^\\d/) && line !== 'Usolgt') { desc = line; }
                            });
                            if (title) items.push({ title, desc, est_low: estLow, est_high: estHigh, hammer, sold });
                        });
                        return items;
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


def filter_furniture(items: list[dict]) -> list[dict]:
    """Filter items to furniture only, excluding ceramics/glass/silver."""
    furniture = []
    for item in items:
        combined = (item.get("title", "") + " " + item.get("desc", "")).lower()
        is_furniture = any(kw in combined for kw in FURNITURE_KEYWORDS)
        is_non_furniture = any(nf in combined for nf in NON_FURNITURE)
        if is_furniture and not is_non_furniture:
            furniture.append(item)
    return furniture


def to_comparables(items: list[dict]) -> list[dict]:
    """Convert Blomqvist items to comparables format for DB import."""
    comparables = []
    for item in items:
        price_nok = item.get("hammer") if item.get("sold") else item.get("est_low")
        if not price_nok:
            continue

        comparables.append({
            "source_name": "Blomqvist",
            "title": f"{item['title']} - {item.get('desc', '')}".strip(" -"),
            "sold_price": round(price_nok * NOK_EUR),
            "currency": "EUR",
            "country": "Norway",
            "confidence": 0.95 if item.get("sold") else 0.60,
            "raw_payload": {
                **item,
                "price_nok": price_nok,
                "price_eur": round(price_nok * NOK_EUR),
                "price_type": "hammer_price" if item.get("sold") else "estimate",
            },
        })
    return comparables
