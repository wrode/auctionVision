#!/usr/bin/env python3
"""Extract clean text from Auctionet HTML snapshots, stripping boilerplate."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from bs4 import BeautifulSoup


def extract_lot_text(html: str) -> str:
    """Extract meaningful lot text from Auctionet HTML, stripping nav/footer/country list."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove script/style/svg/noscript
    for tag in soup(["script", "style", "noscript", "svg", "link"]):
        tag.decompose()

    # Remove the country select dropdown (it's a massive list)
    for select in soup.find_all("select"):
        select.decompose()
    # Also remove any element that looks like the country list container
    for div in soup.find_all(class_=re.compile(r"country|transport|delivery|cookie")):
        div.decompose()

    # Extract structured sections
    parts = []

    # Title from <h1>
    h1 = soup.find("h1")
    if h1:
        parts.append(f"Title: {h1.get_text(strip=True)}")

    # Page title (has category info)
    title_tag = soup.find("title")
    if title_tag:
        parts.append(f"Page title: {title_tag.get_text(strip=True)}")

    # Breadcrumbs
    breadcrumbs = []
    for a in soup.find_all("a"):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        if "/en/search?" in href and text and len(text) < 50:
            breadcrumbs.append(text)
    if breadcrumbs:
        parts.append(f"Breadcrumbs: {' > '.join(breadcrumbs)}")

    # H2 sections (Description, Condition, Artist/designer, Resale right)
    seen_headings = set()
    for h2 in soup.find_all("h2"):
        heading = h2.get_text(strip=True)
        key = heading.lower()
        if key in ("description", "condition", "resale right", "artist/designer") and key not in seen_headings:
            seen_headings.add(key)
            next_el = h2.find_next_sibling()
            if next_el:
                content = next_el.get_text(strip=True)
                content = re.sub(r"Show more$", "", content).strip()
                if content:
                    parts.append(f"{heading}: {content}")

    # Bidding info - extract from raw HTML to avoid bleed
    html_str = str(soup)

    # Current bid
    bid_match = re.search(r"Highest bid:\s*</?\w[^>]*>\s*(?:No bids|(\d[\d\s,]*)\s*EUR)", html_str)
    if bid_match:
        parts.append(f"Highest bid: {bid_match.group(1) or 'No bids'} EUR")

    # Estimate
    est_match = re.search(r"Estimate:\s*(\d[\d\s,]*)\s*EUR", html_str)
    if est_match:
        parts.append(f"Estimate: {est_match.group(1)} EUR")

    # Minimum bid
    min_match = re.search(r"Minimum bid:\s*(\d[\d\s,]*)\s*EUR", html_str)
    if min_match:
        parts.append(f"Minimum bid: {min_match.group(1)} EUR")

    # End time
    end_match = re.search(r"(\d{1,2}\s+\w{3}\s+\d{4}\s+at\s+\d{1,2}:\d{2}\s*\w*)", html_str)
    if end_match:
        parts.append(f"Ends: {end_match.group(1)}")

    # Time remaining
    time_match = re.search(r"Ends in:\s*</?\w[^>]*>\s*(\d+\s+\w+)", html_str)
    if time_match:
        parts.append(f"Time left: {time_match.group(1)}")

    # Location
    loc_match = re.search(r"Item is located in\s+([^<]+)", html_str)
    if loc_match:
        parts.append(f"Location: {loc_match.group(1).strip()}")

    # Auction house from logo
    logo = soup.find(class_="header-and-logo__logo")
    if logo:
        img = logo.find("img")
        if img and img.get("alt"):
            parts.append(f"Auction house: {img['alt']}")

    # House from details section
    house_match = re.search(r"House\s*</?\w[^>]*>\s*([^<]+)", html_str)
    if house_match:
        house = house_match.group(1).strip()
        if house and len(house) < 100:
            parts.append(f"House: {house}")

    # Visits
    visits_match = re.search(r"Visits:\s*(\d+)", html_str)
    if visits_match:
        parts.append(f"Visits: {visits_match.group(1)}")

    # Images - extract URLs
    image_urls = []
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if "item_" in src and "large_" in src:
            image_urls.append(src)
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        image_urls.insert(0, og["content"])
    image_urls = list(dict.fromkeys(image_urls))[:5]
    if image_urls:
        parts.append(f"Images ({len(image_urls)}): {', '.join(image_urls)}")

    return "\n".join(parts)


if __name__ == "__main__":
    for path in sys.argv[1:]:
        html = Path(path).read_text()
        print(f"=== {Path(path).name} ===")
        print(extract_lot_text(html))
        print()
