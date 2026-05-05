import re
from datetime import date
from typing import List, Optional

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
            url = f"https://www.ums.ch/en/search?location={neigh}+Zürich&price_from={price_min}&price_to={price_max}&type=apartment"

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

                        price_match = re.search(r"CHF\s*([\d']+)", text)
                        price = (
                            float(price_match.group(1).replace("'", ""))
                            if price_match
                            else 0
                        )
                        if price < price_min or price > price_max:
                            continue

                        title = "Temporary Apartment"
                        avail_match = re.search(
                            r"(?:ab|from|verfügbar)\s*([\d.]+)", text, re.I
                        )
                        available_from = None
                        if avail_match:
                            available_from = parse_available_from(
                                avail_match.group(1)
                            )  # reuse function from other files

                        listing = ApartmentListing(
                            id=href.split("/")[-1] if href else f"ums-{len(results)}",
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
