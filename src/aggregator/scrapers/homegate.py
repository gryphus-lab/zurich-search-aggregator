import re
from datetime import date
from typing import List, Optional

from playwright.sync_api import sync_playwright

from ..models import ApartmentListing
from ..logger import logger
from ..utils import parse_available_from


def scrape_homegate(
    price_min: int = 1700,
    price_max: int = 3000,
    neighborhoods: List[str] = None,
    move_in_from: Optional[date] = None,
    max_pages: int = 5,
) -> List[ApartmentListing]:
    """
    Scrapes Homegate apartment listings for specified Zurich neighborhoods, price range, and optional earliest move-in date.
    
    Parameters:
        price_min (int): Minimum price in CHF to include.
        price_max (int): Maximum price in CHF to include.
        neighborhoods (List[str] | None): Neighborhood names to search; defaults to ["Oerlikon", "Seebach", "Wipkingen", "Altstetten"] when None.
        move_in_from (date | None): If provided, only include listings with an available-from date on or after this date.
        max_pages (int): Maximum number of paginated result pages to fetch per neighborhood.
    
    Returns:
        List[ApartmentListing]: Collected apartment listings matching the filters, each populated with metadata such as id, title, price_chf, neighborhood, link, available_from, size_m2, source="homegate", furnished=True, a truncated description_snippet, and raw_data.
    """
    if neighborhoods is None:
        neighborhoods = ["Oerlikon", "Seebach", "Wipkingen", "Altstetten"]

    results: List[ApartmentListing] = []

    logger.info(
        f"Starting Homegate scraper | Price: {price_min}-{price_max} CHF | Neighborhoods: {neighborhoods}"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        )
        page = context.new_page()

        for neigh in neighborhoods:
            # Homegate search URL
            url = (
                f"https://www.homegate.ch/en/rent/furnished-dwelling/district-{neigh.lower()}/matching-list"
                f"?ag={price_min}&ah={price_max}"
            )

            logger.info(f"Scraping Homegate → {neigh} | URL: {url}")

            for page_num in range(1, max_pages + 1):
                current_url = f"{url}&ep={page_num}" if page_num > 1 else url

                try:
                    page.goto(current_url, wait_until="domcontentloaded", timeout=90000)
                    page.wait_for_timeout(6000)

                    # Scroll
                    page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                    page.wait_for_timeout(3000)

                    cards = page.locator(
                        "article[data-test='result-item'], div[data-test='listing-card']"
                    ).all()

                    added = 0
                    for card in cards:
                        try:
                            text = card.inner_text().strip()
                            if len(text) < 40:
                                continue

                            link_elem = card.locator("a").first
                            href = link_elem.get_attribute("href") or ""
                            link = (
                                "https://www.homegate.ch" + href
                                if href.startswith("/")
                                else href
                            )
                            if not link:
                                continue

                            # Price
                            price_match = re.search(r"CHF\s*([\d',]+)", text)
                            price = (
                                float(
                                    price_match.group(1)
                                    .replace("'", "")
                                    .replace(",", "")
                                )
                                if price_match
                                else 0
                            )
                            if price < price_min or price > price_max:
                                continue

                            # Title / rooms
                            title_match = re.search(
                                r"(\d+(?:\s*[½1/2])?\s*Zimmer)", text, re.I
                            )
                            title = title_match.group(0) if title_match else "Apartment"

                            # Available from
                            avail_match = re.search(
                                r"(?:ab|verfügbar|available(?:\s+from)?)\s*([\d.\-\sa-zA-Z]{5,20})",
                                text,
                                re.I,
                            )
                            avail_str = avail_match.group(1) if avail_match else None
                            available_from = parse_available_from(avail_str)

                            if (
                                move_in_from
                                and available_from
                                and available_from < move_in_from
                            ):
                                continue

                            size_match = re.search(r"(\d+)\s*m²", text)
                            size_m2 = float(size_match.group(1)) if size_match else None

                            # Normalize href and extract ID
                            normalized_href = href.rstrip('/') if href else ""
                            listing_id = normalized_href.split("/")[-1] if normalized_href else ""
                            listing = ApartmentListing(
                                id=listing_id if listing_id else f"hg-{len(results)}",
                                title=title,
                                price_chf=price,
                                neighborhood=neigh,
                                address=neigh,
                                link=link,
                                available_from=available_from,
                                size_m2=size_m2,
                                rooms=None,
                                source="homegate",
                                furnished=True,
                                description_snippet=text[:450],
                                raw_data={"raw_text": text},
                            )

                            # Mark flexible
                            if any(
                                k in text.lower()
                                for k in [
                                    "befristet",
                                    "temporary",
                                    "kurzfristig",
                                    "möbliert",
                                ]
                            ):
                                listing.description_snippet = (
                                    "[FLEXIBLE] " + listing.description_snippet
                                )

                            results.append(listing)
                            added += 1

                        except Exception:
                            continue

                    logger.info(
                        f"Homegate {neigh} page {page_num}: Added {added} listings"
                    )

                except Exception as e:
                    logger.error(f"Homegate {neigh} page {page_num} failed: {e}")

        browser.close()

    logger.info(f"Homegate scraper finished. Total: {len(results)} listings")
    return results
