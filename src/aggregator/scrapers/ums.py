import re
from datetime import date
from typing import List, Optional

from playwright.sync_api import sync_playwright

from ..locations import coords_for, default_zurich_quartiers
from ..logger import logger
from ..models import ApartmentListing
from ..utils import parse_available_from


_DEFAULT_NEIGHBORHOODS = default_zurich_quartiers()


def _extract_price(text: str) -> float:
    match = re.search(r"CHF\s*([\d'’]+)", text)
    if match is None:
        return 0.0
    return float(match.group(1).replace("'", "").replace("’", ""))


def _extract_title(text: str) -> str:
    patterns = [
        r"(\d+\s*room)",
        r"(\d+\s*zimmer)",
        r"(\d+\s*[½1/2]\s*room)",
        r"(\d+\s*[½1/2]\s*zimmer)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1)

    for size_pattern in (
        r"(\d+(?:[.,]\d+)?)\s*m²",
        r"(\d+(?:[.,]\d+)?)\s*m2",
        r"(\d+(?:[.,]\d+)?)\s*sqm",
    ):
        match = re.search(size_pattern, text, re.I)
        if match:
            return f"{match.group(1).replace(',', '.')}m² Apartment"

    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return "Temporary Apartment"


def _extract_available_from(text: str) -> Optional[date]:
    match = re.search(r"(?:ab|from|verfügbar)\s+([^\n\r]{5,20})", text, re.I)
    if match is None:
        return None
    return parse_available_from(match.group(1))


def _extract_size_m2(text: str) -> Optional[float]:
    for size_pattern in (
        r"(\d+(?:[.,]\d+)?)\s*m²",
        r"(\d+(?:[.,]\d+)?)\s*m2",
        r"(\d+(?:[.,]\d+)?)\s*sqm",
    ):
        match = re.search(size_pattern, text, re.I)
        if match:
            return float(match.group(1).replace(",", "."))
    return None


def _build_link(href: str) -> str:
    if not href:
        return ""
    return "https://www.ums.ch" + href if href.startswith("/") else href


def _is_flexible(text: str) -> bool:
    lowered = text.lower()
    keywords = ["befristet", "temporary", "kurzfristig", "möbliert", "furnished"]
    return any(keyword in lowered for keyword in keywords)


def _debug_first_card(cards) -> None:
    if not cards:
        return
    try:
        first_text = cards[0].inner_text().strip()[:400]
        logger.debug(f"FIRST UMS CARD PREVIEW:\n{first_text}\n---")
    except Exception:
        logger.debug("FIRST UMS CARD PREVIEW unavailable; skipping debug snapshot")


def _listing_from_card(
    card,
    neigh: str,
    price_min: int,
    price_max: int,
    move_in_from: Optional[date],
    index: int,
) -> Optional[ApartmentListing]:
    text = card.inner_text().strip()
    if len(text) < 30:
        return None

    link_elem = card.locator("a").first
    href = link_elem.get_attribute("href") or ""
    link = _build_link(href)
    if not link:
        return None

    price = _extract_price(text)
    if price < price_min or price > price_max:
        return None

    title = _extract_title(text)
    available_from = _extract_available_from(text)
    if move_in_from and available_from and available_from < move_in_from:
        return None

    description_snippet = text[:400]
    if _is_flexible(text):
        description_snippet = "[FLEXIBLE] " + description_snippet

    return ApartmentListing(
        id=href.split("/")[-1] if href else f"ums-{index}",
        title=title,
        price_chf=price,
        neighborhood=neigh,
        address=neigh,
        link=link,
        available_from=available_from,
        size_m2=_extract_size_m2(text),
        rooms=None,
        source="ums",
        furnished=True,
        description_snippet=description_snippet,
        raw_data={"raw_text": text},
    )


def _scrape_neighborhood_cards(
    page, neigh: str, price_min: int, price_max: int, move_in_from: Optional[date]
) -> List[ApartmentListing]:
    lat, lng = coords_for(neigh)
    url = f"https://www.ums.ch/furnished-apartments/{neigh}/{lat}/{lng}/"
    logger.info(f"Scraping UMS → {neigh} | URL: {url}")

    page.goto(url, wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(10000)

    for _ in range(6):
        page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        page.wait_for_timeout(4000)

    cards = page.locator(
        "div.ad, article, div.listing-item, div.search-result, div[class*='listing']"
    ).all()
    logger.info(f"Found {len(cards)} potential cards for {neigh}")
    _debug_first_card(cards)

    results: List[ApartmentListing] = []
    for index, card in enumerate(cards):
        try:
            listing = _listing_from_card(
                card, neigh, price_min, price_max, move_in_from, index
            )
        except Exception:
            continue
        if listing is not None:
            results.append(listing)

    logger.info(f"UMS {neigh}: Added {len(results)} listings")
    return results


def scrape_ums(
    price_min: int = 1700,
    price_max: int = 3000,
    neighborhoods: Optional[List[str]] = None,
    move_in_from: Optional[date] = None,
) -> List[ApartmentListing]:
    """Scrape apartment listings from ums.ch for the specified Zurich neighborhoods and price range."""
    if neighborhoods is None:
        neighborhoods = _DEFAULT_NEIGHBORHOODS

    results: List[ApartmentListing] = []
    logger.info(
        f"Starting UMS scraper | Price: {price_min}-{price_max} CHF | Neighborhoods: {neighborhoods}"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        )
        page = context.new_page()

        for neigh in neighborhoods:
            try:
                results.extend(
                    _scrape_neighborhood_cards(
                        page, neigh, price_min, price_max, move_in_from
                    )
                )
            except Exception as e:
                logger.error(f"UMS {neigh} failed: {e}")

        browser.close()

    logger.info(f"UMS scraper finished. Total listings: {len(results)}")
    return results
