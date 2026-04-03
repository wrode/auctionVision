"""Fetcher for Finn.no 'Ønskes kjøpt' (wanted to buy) listings."""

import asyncio
import logging
import re
from typing import Any

from playwright.async_api import async_playwright

from backend.config import load_yaml_config

logger = logging.getLogger(__name__)


class FinnWantedFetcher:
    """Scrapes Finn.no wanted listings and marks high-value items."""

    def __init__(self):
        config = load_yaml_config("finn_wanted.yaml")
        finn = config.get("finn", {})
        self.base_url = finn.get("base_url", "https://www.finn.no")
        self.trade_type = finn.get("trade_type", 3)
        rate = finn.get("rate_limit", {})
        self.delay = rate.get("delay_between_requests_seconds", 3)
        self.max_pages = rate.get("max_pages_per_category", 10)
        self.categories = finn.get("categories", [])

        filters = config.get("filters", {})
        self.min_price = filters.get("min_price_nok", 1000)
        self.high_value_brands = {b.lower() for b in filters.get("high_value_brands", [])}
        self.high_value_designers = [d.lower() for d in filters.get("high_value_designers", [])]

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
            logger.info("Initialized Playwright browser for Finn")

    async def fetch_all_categories(self) -> list[dict[str, Any]]:
        """Fetch wanted listings across all configured categories.

        Returns:
            List of all wanted listing dicts, each with ``is_high_value``
            and ``match_reason`` fields set.
        """
        await self._init_browser()
        all_listings = []
        seen_ids = set()

        for cat in self.categories:
            sub_cat = cat["sub_category"]
            cat_name = cat["name"]
            logger.info(f"Fetching wanted listings: {cat_name} ({sub_cat})")

            for page_num in range(1, self.max_pages + 1):
                url = (
                    f"{self.base_url}/recommerce/forsale/search"
                    f"?sub_category={sub_cat}&trade_type={self.trade_type}&page={page_num}"
                )
                listings = await self._fetch_listing_page(url, cat_name)

                if not listings:
                    logger.info(f"  No more results on page {page_num}, moving to next category")
                    break

                new_count = 0
                for listing in listings:
                    fid = listing["finn_id"]
                    if fid not in seen_ids:
                        seen_ids.add(fid)
                        listing["category"] = cat_name
                        all_listings.append(listing)
                        new_count += 1

                logger.info(f"  Page {page_num}: {len(listings)} listings, {new_count} new")
                await asyncio.sleep(self.delay)

        # Mark high-value listings but keep ALL
        high_count = 0
        for listing in all_listings:
            reason = self._is_high_value(listing)
            if reason:
                listing["is_high_value"] = True
                listing["match_reason"] = reason
                high_count += 1
            else:
                listing["is_high_value"] = False
                listing["match_reason"] = None

        logger.info(
            f"Total: {len(all_listings)} wanted listings, "
            f"{high_count} high-value"
        )
        return all_listings

    async def _fetch_listing_page(self, url: str, category_name: str) -> list[dict[str, Any]]:
        """Fetch and parse a single listing page.

        Uses JavaScript extraction to pull structured data from article elements.
        """
        try:
            await self.page.goto(url, wait_until="networkidle", timeout=30000)

            # Extract listing data via JS - articles are in the main DOM
            listings = await self.page.evaluate("""() => {
                const articles = document.querySelectorAll('article');
                const results = [];

                for (const article of articles) {
                    // Find the main link with finn item URL
                    const link = article.querySelector('a[href*="/recommerce/forsale/item/"]');
                    if (!link) continue;

                    const url = link.href;
                    const finnIdMatch = url.match(/\\/item\\/(\\d+)/);
                    if (!finnIdMatch) continue;

                    const finnId = finnIdMatch[1];
                    const title = link.textContent.trim();

                    // Get all direct text-bearing children (spans, divs, etc.)
                    // Skip the heading/link and images
                    const textEls = [];
                    for (const child of article.children) {
                        const tag = child.tagName.toLowerCase();
                        if (tag === 'img' || tag === 'region' || tag === 'a') continue;
                        if (child.querySelector('a[href*="/item/"]')) continue;
                        const txt = child.textContent.trim();
                        if (txt && txt.length > 0) textEls.push(txt);
                    }

                    // Parse price: look for pattern "X kr" or "X XXX kr"
                    let offeredPrice = null;
                    const priceTexts = textEls.filter(t => /^[\\d\\s]+kr$/.test(t.replace(/\\./g, '')));
                    if (priceTexts.length > 0) {
                        const priceStr = priceTexts[0].replace(/\\s/g, '').replace('kr', '');
                        offeredPrice = parseInt(priceStr, 10);
                        if (isNaN(offeredPrice)) offeredPrice = null;
                    }

                    // Non-price, non-"Ønskes kjøpt" text elements are brand/location/time
                    const metaTexts = textEls.filter(t =>
                        !/^[\\d\\s]+kr$/.test(t.replace(/\\./g, '')) &&
                        t !== 'Ønskes kjøpt' &&
                        t !== 'Betalt plassering' &&
                        !t.startsWith('Legg til') &&
                        !t.startsWith('Ikon med') &&
                        !t.startsWith('Image nav') &&
                        !t.startsWith('Product image')
                    );

                    // Last element is usually time (e.g. "5 t.", "2 dg.", "16. mars")
                    // Second-to-last is location
                    // If there's a third, it's brand
                    let brand = null;
                    let location = null;
                    let publishedText = null;

                    if (metaTexts.length >= 3) {
                        brand = metaTexts[metaTexts.length - 3];
                        location = metaTexts[metaTexts.length - 2];
                        publishedText = metaTexts[metaTexts.length - 1];
                    } else if (metaTexts.length === 2) {
                        location = metaTexts[0];
                        publishedText = metaTexts[1];
                    } else if (metaTexts.length === 1) {
                        publishedText = metaTexts[0];
                    }

                    // Extract image URLs
                    const images = [];
                    for (const img of article.querySelectorAll('img')) {
                        const src = img.src || img.dataset?.src;
                        if (src && !src.includes('data:') && !src.includes('annonsering')) {
                            images.push(src);
                        }
                    }

                    results.push({
                        finn_id: finnId,
                        url: url,
                        title: title,
                        offered_price: offeredPrice,
                        brand: brand,
                        buyer_location: location,
                        published_text: publishedText,
                        image_urls: images,
                    });
                }
                return results;
            }""")

            return listings

        except Exception as e:
            logger.error(f"Error fetching listing page {url}: {e}")
            return []

    def _is_high_value(self, listing: dict) -> str | None:
        """Check if a listing qualifies as high-value.

        Returns match reason string, or None if not high-value.
        """
        title_lower = listing.get("title", "").lower()
        brand_lower = (listing.get("brand") or "").lower()
        price = listing.get("offered_price")

        # Check brand match
        if brand_lower and brand_lower in self.high_value_brands:
            return f"brand:{listing['brand']}"

        # Check designer/model match in title
        for designer in self.high_value_designers:
            if designer in title_lower:
                return f"designer:{designer}"

        # Check price floor (if price stated and high enough, keep it even without brand match)
        if price and price >= self.min_price:
            return f"price:{price} NOK"

        return None

    async def close(self):
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        logger.info("Closed Finn browser")
