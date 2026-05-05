import re
from datetime import date
from typing import List, Optional
from urllib.parse import quote_plus

from playwright.sync_api import sync_playwright

from ..models import ApartmentListing
from ..logger import logger
from ..utils import parse_available_from


def scrape_ums(
    price_min: int = 1700,
    price_max: int = 3000,
    neighborhoods: List[str] = None,
    move_in_from: Optional[date] = None,
) -> List[ApartmentListing]:
    """
    Scrapes apartment listings from ums.ch for the specified Zurich neighborhoods and price range.
    
    Builds and returns apartment records extracted from search result pages on https://www.ums.ch. Each returned listing includes parsed price, resolved link, neighborhood/address, optional parsed availability date (when present), a description snippet, and raw extracted text. Listings with prices outside the provided [price_min, price_max] range are excluded.
    
    Parameters:
        price_min (int): Minimum rent in CHF to include (default: 1700).
        price_max (int): Maximum rent in CHF to include (default: 3000).
        neighborhoods (List[str], optional): Neighborhood names to search. When omitted, defaults to ["Oerlikon", "Seebach", "Wipkingen", "Altstetten"].
        move_in_from (Optional[date]): Optional move-in date parameter (accepted but not used by this function).
    
    Returns:
        List[ApartmentListing]: A list of ApartmentListing objects matching the search filters; each entry contains parsed fields such as `id`, `title`, `price_chf`, `neighborhood`, `address`, `link`, `available_from` (if parsed), `description_snippet`, and `raw_data`.
    """
    if neighborhoods is None:
        neighborhoods = ["Oerlikon", "Seebach", "Wipkingen", "Altstetten"]

    results: List[ApartmentListing] = []

    logger.info(f"Starting UMS scraper | Price: {price_min}-{price_max} CHF")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        )
        page = context.new_page()

        for neigh in neighborhoods:
            # Use path-based URL structure for furnished apartments
            location_encoded = quote_plus(f"{neigh} Zürich")
            # Using generic lat/lng for Zurich center as placeholder
            url = f"https://www.ums.ch/furnished-apartments/{location_encoded}/47.3769/8.5417/"

            logger.info(f"Scraping UMS → {neigh} | URL: {url}")

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=90000)
                page.wait_for_timeout(6000)

                cards = page.locator("div.ad, article, div.listing-item").all()

                added = 0
                for card in cards:
                    try:
                        text = card.inner_text().strip()
                        if len(text) < 30:
                            continue

                        link_elem = card.locator("a").first
                        href = link_elem.get_attribute("href") or ""
                        link = (
                            "https://www.ums.ch" + href
                            if href.startswith("/")
                            else href
                        )
                        if not link:
                            continue

                        price_match = re.search(r"CHF\s*([\d'\u2019]+)", text)
                        price = (
                            float(price_match.group(1).replace("'", "").replace("\u2019", ""))
                            if price_match
                            else 0
                        )
                        if price < price_min or price > price_max:
                            continue

                        # Derive title from room count or size if available, otherwise use text snippet
                        room_match = re.search(r"(\d+(?:\s*[½1/2])?\s*[Rr]oom|[Zz]immer)", text, re.I)
                        size_match = re.search(r"(\d+)\s*m²", text)
                        if room_match:
                            title = room_match.group(0)
                        elif size_match:
                            title = f"{size_match.group(1)}m² Apartment"
                        else:
                            title = text[:50].split('\n')[0] if text else "Temporary Apartment"

                        # Extract availability with broader pattern
                        avail_match = re.search(
                            r"(?:ab|from|verfügbar|available)\s+([\w\s\d./-]+?)(?:\s|$)", text, re.I
                        )
                        available_from = None
                        if avail_match:
                            available_from = parse_available_from(
                                avail_match.group(1).strip()
                            )

                        # Normalize href by stripping trailing slashes before extracting ID
                        normalized_href = href.rstrip('/') if href else ""
                        listing = ApartmentListing(
                            id=normalized_href.split("/")[-1] if normalized_href else f"ums-{len(results)}",
                            title=title,
                            price_chf=price,
                            neighborhood=neigh,
                            address=neigh,
                            link=link,
                            available_from=available_from,
                            size_m2=None,
                            rooms=None,
                            source="ums",
                            furnished=True,
                            description_snippet=text[:400],
                            raw_data={"raw_text": text},
                        )

                        if any(
                            k in text.lower()
                            for k in ["befristet", "temporary", "möbliert"]
                        ):
                            listing.description_snippet = (
                                "[FLEXIBLE] " + listing.description_snippet
                            )

                        results.append(listing)
                        added += 1

                    except Exception:
                        continue

                logger.info(f"UMS {neigh}: Added {added} listings")

            except Exception as e:
                logger.error(f"UMS {neigh} failed: {e}")

        browser.close()

    logger.info(f"UMS scraper finished. Total: {len(results)} listings")
    return results
