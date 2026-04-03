"""Finn.no for-sale market data scraper.

Does targeted searches by designer/brand name to build market snapshots:
- How many items are listed for sale in Norway
- Price distribution (avg, median, min, max)
- Sample listings for reference
"""

import asyncio
import logging
import re
import statistics
from typing import Any
from urllib.parse import quote_plus

from playwright.async_api import async_playwright

from backend.config import load_yaml_config

logger = logging.getLogger(__name__)

FURNITURE_KEYWORDS = {
    # Norwegian
    "stol", "bord", "sofa", "skap", "hylle", "lampe", "kommode",
    "lenestol", "spisestol", "salongbord", "spisebord", "skrivebord",
    "bokhylle", "seng", "benk", "krakk", "puff", "reol",
    # Swedish
    "fåtölj", "soffa", "skåp", "byrå", "sideboard", "pall",
    "soffbord", "matbord",
    # English
    "chair", "table", "sofa", "desk", "shelf", "cabinet", "stool",
    "armchair", "sideboard", "lamp", "pendant", "daybed", "bench",
    # Design terms
    "teak", "danish", "dansk", "vintage", "retro", "mid-century",
    "design", "møbel", "møbler", "furniture", "interiør",
}


class FinnForSaleScraper:
    """Scrapes Finn.no for-sale listings by designer/brand to build market snapshots."""

    @staticmethod
    def _extract_finn_id(url: str) -> str | None:
        """Extract Finn item ID from URL like .../item/458334960"""
        match = re.search(r'/item/(\d+)', url)
        return match.group(1) if match else None

    def __init__(self):
        config = load_yaml_config("finn_wanted.yaml")
        finn = config.get("finn", {})
        self.base_url = finn.get("base_url", "https://www.finn.no")
        rate = finn.get("rate_limit", {})
        self.delay = rate.get("delay_between_requests_seconds", 3)

        filters = config.get("filters", {})
        self.high_value_brands = filters.get("high_value_brands", [])
        self.high_value_designers = filters.get("high_value_designers", [])

        self.browser = None
        self.context = None
        self.page = None

    async def _init_browser(self):
        if self.browser is None:
            pw = await async_playwright().start()
            self.browser = await pw.chromium.launch(headless=True)
            self.context = await self.browser.new_context(
                locale="nb-NO",
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            )
            self.page = await self.context.new_page()
            logger.info("Initialized Playwright browser for Finn for-sale scraper")

    async def fetch_market_data(self) -> tuple[list[dict], list[dict]]:
        """Fetch for-sale market data for all configured designers and brands.

        Returns:
            Tuple of (market_stats_list, all_raw_listings_with_metadata).
            The first element is the aggregated stats per query (unchanged).
            The second element is the individual listings with query metadata
            attached, for storage in FinnForSaleListing.
        """
        await self._init_browser()
        stats_results = []
        all_listings = []

        # Search for each designer
        total_queries = len(self.high_value_designers) + len(self.high_value_brands)
        completed = 0

        for designer in self.high_value_designers:
            completed += 1
            logger.info(f"[{completed}/{total_queries}] Searching for-sale: designer '{designer}'")
            listings = await self._search_forsale(designer, max_pages=3)
            stats = self._compute_stats(designer, "designer", listings)
            stats_results.append(stats)
            logger.info(
                f"  -> {stats['listing_count']} listings, "
                f"median {stats.get('median_price_nok', 'N/A')} NOK"
            )

            # Attach query metadata to each listing for DB storage
            for listing in listings:
                finn_id = self._extract_finn_id(listing.get("url", ""))
                if finn_id:
                    all_listings.append({
                        "finn_id": finn_id,
                        "url": listing.get("url", ""),
                        "title": listing.get("title", ""),
                        "price_nok": listing.get("price"),
                        "brand": listing.get("brand"),
                        "location": listing.get("location"),
                        "search_query": designer,
                        "query_type": "designer",
                    })

        # Search for each brand
        for brand in self.high_value_brands:
            completed += 1
            logger.info(f"[{completed}/{total_queries}] Searching for-sale: brand '{brand}'")
            listings = await self._search_forsale(brand, max_pages=3)
            stats = self._compute_stats(brand, "brand", listings)
            stats_results.append(stats)
            logger.info(
                f"  -> {stats['listing_count']} listings, "
                f"median {stats.get('median_price_nok', 'N/A')} NOK"
            )

            # Attach query metadata to each listing for DB storage
            for listing in listings:
                finn_id = self._extract_finn_id(listing.get("url", ""))
                if finn_id:
                    all_listings.append({
                        "finn_id": finn_id,
                        "url": listing.get("url", ""),
                        "title": listing.get("title", ""),
                        "price_nok": listing.get("price"),
                        "brand": listing.get("brand"),
                        "location": listing.get("location"),
                        "search_query": brand,
                        "query_type": "brand",
                    })

        logger.info(
            f"Completed {len(stats_results)} market data queries, "
            f"{len(all_listings)} individual listings extracted"
        )
        return stats_results, all_listings

    async def _search_forsale(self, query: str, max_pages: int = 3) -> list[dict]:
        """Search Finn for-sale listings for a given query term.

        Args:
            query: Search term (designer name, brand, etc.)
            max_pages: Maximum number of result pages to scrape.

        Returns:
            List of listing dicts with title, price, location, url.
        """
        all_listings = []
        encoded_query = quote_plus(query)

        for page_num in range(1, max_pages + 1):
            url = (
                f"{self.base_url}/recommerce/forsale/search"
                f"?trade_type=1&q={encoded_query}&page={page_num}"
            )

            try:
                await self.page.goto(url, wait_until="networkidle", timeout=30000)

                # Extract listing data from Schema.org JSON-LD embedded in page.
                # Finn renders a CollectionPage > ItemList > ListItem[] with
                # Product objects that have name, price, brand, url.
                listings = await self.page.evaluate("""() => {
                    const results = [];
                    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                    for (const script of scripts) {
                        try {
                            const data = JSON.parse(script.textContent);
                            // Find the CollectionPage or ItemList
                            let items = [];
                            if (data['@type'] === 'CollectionPage' && data.mainEntity) {
                                items = data.mainEntity.itemListElement || [];
                            } else if (data['@type'] === 'ItemList') {
                                items = data.itemListElement || [];
                            }
                            for (const entry of items) {
                                const product = entry.item || entry;
                                if (!product || product['@type'] !== 'Product') continue;
                                let price = null;
                                if (product.offers) {
                                    const p = parseInt(product.offers.price, 10);
                                    if (!isNaN(p) && p > 0) price = p;
                                }
                                const brand = product.brand
                                    ? (product.brand.name || product.brand)
                                    : null;
                                results.push({
                                    title: product.name || '',
                                    price: price,
                                    brand: brand,
                                    url: product.url || '',
                                    location: null,
                                });
                            }
                        } catch (e) { /* skip malformed JSON-LD */ }
                    }
                    // Fallback: if no JSON-LD items, try DOM links
                    if (results.length === 0) {
                        const links = document.querySelectorAll('a[href*="/recommerce/forsale/item/"]');
                        const seen = new Set();
                        for (const link of links) {
                            const url = link.href;
                            const idMatch = url.match(/\\/item\\/(\\d+)/);
                            if (!idMatch || seen.has(idMatch[1])) continue;
                            seen.add(idMatch[1]);
                            // Walk up to find text context
                            const container = link.closest('article') || link.parentElement;
                            const text = container ? container.innerText : '';
                            const lines = text.split('\\n').map(l => l.trim()).filter(Boolean);
                            const title = lines[0] || '';
                            let price = null;
                            for (const line of lines) {
                                const m = line.match(/^([\\d\\s]+)\\s*kr$/);
                                if (m) {
                                    price = parseInt(m[1].replace(/\\s/g, ''), 10);
                                    if (isNaN(price)) price = null;
                                    break;
                                }
                            }
                            results.push({ title, price, brand: null, url, location: null });
                        }
                    }
                    return results;
                }""")

                # Try to extract total result count from the page
                if page_num == 1:
                    try:
                        total_text = await self.page.evaluate("""() => {
                            const body = document.body.innerText;
                            const match = body.match(/(\\d[\\d\\s]*) treff/);
                            return match ? match[1].replace(/\\s/g, '') : null;
                        }""")
                        if total_text:
                            logger.info(f"  Total results for '{query}': {total_text}")
                    except Exception:
                        pass

                if not listings:
                    logger.info(f"  No more results on page {page_num}")
                    break

                all_listings.extend(listings)
                logger.info(f"  Page {page_num}: {len(listings)} listings extracted")

                # Rate limit
                await asyncio.sleep(self.delay)

            except Exception as e:
                logger.error(f"Error fetching for-sale page {url}: {e}")
                await asyncio.sleep(self.delay)
                break

        return all_listings

    def _is_furniture_listing(self, title: str) -> bool:
        """Check if a listing title is likely furniture-related."""
        title_lower = title.lower()
        return any(kw in title_lower for kw in FURNITURE_KEYWORDS)

    def _compute_stats(self, query: str, query_type: str, listings: list[dict]) -> dict:
        """Compute market statistics from scraped listings.

        Args:
            query: The search query (designer/brand name).
            query_type: "designer" or "brand".
            listings: Raw listing dicts from _search_forsale.

        Returns:
            Dict with aggregated market data ready for DB insertion.
        """
        # Filter to furniture-relevant listings to avoid noisy results
        # from common names matching unrelated items
        furniture_listings = [
            l for l in listings if self._is_furniture_listing(l.get("title", ""))
        ]

        prices = [l["price"] for l in furniture_listings if l.get("price") and l["price"] > 0]

        stats: dict[str, Any] = {
            "query_type": query_type,
            "query_value": query,
            "finn_category": None,  # broad search, no specific category
            "listing_count": len(furniture_listings),
        }

        if prices:
            stats["avg_price_nok"] = round(sum(prices) / len(prices), 0)
            stats["median_price_nok"] = round(statistics.median(prices), 0)
            stats["min_price_nok"] = min(prices)
            stats["max_price_nok"] = max(prices)
            stats["price_samples"] = sorted(prices)
        else:
            stats["avg_price_nok"] = None
            stats["median_price_nok"] = None
            stats["min_price_nok"] = None
            stats["max_price_nok"] = None
            stats["price_samples"] = []

        # Collect sample listings (first 5)
        sample_listings = []
        for l in furniture_listings[:5]:
            sample_listings.append({
                "title": l.get("title"),
                "price": l.get("price"),
                "url": l.get("url"),
            })
        stats["sample_listings"] = sample_listings

        return stats

    async def close(self):
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        logger.info("Closed Finn for-sale browser")
