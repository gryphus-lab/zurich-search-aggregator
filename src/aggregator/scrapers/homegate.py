import re
from datetime import date
from typing import List, Optional
from urllib.parse import quote

from playwright.sync_api import sync_playwright

from ..models import ApartmentListing
from ..logger import logger
from ..utils import parse_available_from


def _build_homegate_url(neigh: str, price_min: int, price_max: int) -> str:
    """
    Build the Homegate rent-search URL for a location.

    Matches Homegate's current scheme:
        https://www.homegate.ch/rent/real-estate/district-<name>/matching-list?ag=<min>&ah=<max>

    City-of-Zurich quartiers use the ``district-<name>`` path. Independent
    metro municipalities use Homegate's free-text location search instead, since
    the district path only resolves inside the city. The ``real-estate``
    category returns all property types (not only furnished dwellings).
    """
    from ..locations import is_zurich_quartier

    base = "https://www.homegate.ch/rent/real-estate"
    price_q = f"?ag={price_min}&ah={price_max}"
    if is_zurich_quartier(neigh):
        return f"{base}/district-{neigh.lower()}/matching-list{price_q}"
    # Metro municipality: free-text location search.
    loc = quote(f"{neigh}, Zürich")
    return f"{base}/matching-list{price_q}&loc={loc}"


# Homegate listing-detail links look like /rent/<numeric-id> (optionally with a
# locale/segment prefix). Anchoring on these is far more stable than guessing a
# data-test attribute on the card wrapper, which Homegate changes often.
_LISTING_HREF_RE = re.compile(r"/\d{6,}")
_DECIMAL_ROOM_RE = re.compile(
    r"\b(?P<count>\d+(?:[.,]\d+)?)\s*(?P<label>rooms?|zimmer)\b",
    re.I,
)
_FRACTION_ROOM_RE = re.compile(
    r"\b(?P<count>\d+)\s*(?P<fraction>½|1/2)\s*(?P<label>rooms?|zimmer)\b",
    re.I,
)

# Preferred result-card selectors, tried in order. The last is a resilient
# fallback: any anchor pointing at a listing-detail URL.
_CARD_SELECTORS = (
    "[data-test='result-list-item']",
    "article[data-test='result-item']",
    "div[data-test='listing-card']",
    "a[href*='/rent/']",
)


def _find_result_cards(page) -> list:
    """
    Return result-card elements, trying progressively more generic selectors.

    Homegate's result markup changes frequently, so rather than depend on one
    attribute we try several known wrappers and finally fall back to the listing
    anchors themselves (filtered to detail links).
    """
    for selector in _CARD_SELECTORS:
        cards = page.locator(selector).all()
        if not cards:
            continue
        # For the anchor fallback, keep only true listing-detail links.
        if selector.startswith("a["):
            cards = [
                c
                for c in cards
                if _LISTING_HREF_RE.search(c.get_attribute("href") or "")
            ]
        if cards:
            return cards
    return []


def _dismiss_consent(page) -> None:
    """
    Dismiss the OneTrust cookie-consent banner if present.

    Homegate shows a OneTrust modal on first visit that overlays the result
    list; the saved page was captured after accepting it. Click the accept
    button (several known selectors / labels) so results render. Best-effort:
    never raise if the banner isn't there.
    """
    selectors = (
        "#onetrust-accept-btn-handler",
        "button#onetrust-accept-btn-handler",
        "[data-test='cookie-accept']",
        "button:has-text('Accept all')",
        "button:has-text('Alle akzeptieren')",
        "button:has-text('Einverstanden')",
        "button:has-text('Zustimmen')",
    )
    for selector in selectors:
        try:
            btn = page.locator(selector).first
            if btn.count() and btn.is_visible():
                btn.click(timeout=3000)
                page.wait_for_timeout(500)
                logger.info("Dismissed cookie consent via %s", selector)
                return
        except Exception:
            continue


def _card_href(card) -> str:
    """
    Extract the listing-detail href from a card.

    Works whether the card *is* the anchor (fallback selector) or *contains*
    one. Prefers an href that looks like a listing-detail link.
    """
    own = card.get_attribute("href") or ""
    if _LISTING_HREF_RE.search(own):
        return own
    for anchor in card.locator("a").all():
        href = anchor.get_attribute("href") or ""
        if _LISTING_HREF_RE.search(href):
            return href
    # Fall back to the first anchor's href (or the card's own, possibly empty).
    first = card.locator("a").first
    return first.get_attribute("href") or own


def _room_title(text: str) -> str:
    """Return Homegate's room count as a title, or a generic fallback."""
    match = _FRACTION_ROOM_RE.search(text)
    if match:
        count = f"{match.group('count')} {match.group('fraction')}".strip()
        return f"{count} {match.group('label').lower()}"

    match = _DECIMAL_ROOM_RE.search(text)
    if match:
        return f"{match.group('count').strip()} {match.group('label').lower()}"

    return "Apartment"


def _price_chf(text: str) -> float:
    match = re.search(r"CHF\s*([\d',]+)", text)
    if not match:
        return 0
    return float(match.group(1).replace("'", "").replace(",", ""))


def _available_from_text(text: str) -> Optional[date]:
    compact_text = " ".join(text.split())
    lower_text = compact_text.lower()
    for prefix in ("available from", "available", "verfügbar", "ab"):
        start = lower_text.find(prefix)
        if start == -1:
            continue
        candidate = compact_text[start + len(prefix) : start + len(prefix) + 24]
        parsed = parse_available_from(candidate.strip(" :-,."))
        if parsed:
            return parsed
    return None


def _size_m2(text: str) -> Optional[float]:
    marker_index = text.find("m²")
    if marker_index == -1:
        return None

    before_marker = text[:marker_index].rstrip()
    digits = []
    for char in reversed(before_marker):
        if not char.isdigit():
            break
        digits.append(char)

    if not digits:
        return None
    return float("".join(reversed(digits)))


def _normalize_link(href: str) -> str:
    return "https://www.homegate.ch" + href if href.startswith("/") else href


def _listing_id(href: str, fallback_index: int) -> str:
    normalized_href = href.rstrip("/") if href else ""
    if normalized_href:
        return normalized_href.split("/")[-1]
    return f"hg-{fallback_index}"


def _parse_card(
    card,
    neigh: str,
    price_min: int,
    price_max: int,
    move_in_from: Optional[date],
    seen_links: set[str],
    fallback_index: int,
) -> Optional[ApartmentListing]:
    text = card.inner_text().strip()
    if len(text) < 40:
        return None

    href = _card_href(card)
    link = _normalize_link(href)
    if not link or link in seen_links:
        return None
    seen_links.add(link)

    price = _price_chf(text)
    if price < price_min or price > price_max:
        return None

    available_from = _available_from_text(text)
    if move_in_from and available_from and available_from < move_in_from:
        return None

    return ApartmentListing(
        id=_listing_id(href, fallback_index),
        title=_room_title(text),
        price_chf=price,
        neighborhood=neigh,
        address=neigh,
        link=link,
        available_from=available_from,
        size_m2=_size_m2(text),
        rooms=None,
        source="homegate",
        furnished=True,
        description_snippet=text[:450],
        raw_data={"raw_text": text},
    )


def _scroll_results(page) -> None:
    for _ in range(4):
        page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        page.wait_for_timeout(1500)


def _wait_for_results(page) -> None:
    try:
        page.wait_for_selector("[data-test='result-list-item']", timeout=15000)
    except Exception:
        page.wait_for_timeout(4000)


def _parse_cards(
    cards: list,
    neigh: str,
    price_min: int,
    price_max: int,
    move_in_from: Optional[date],
    fallback_start: int,
) -> List[ApartmentListing]:
    listings: List[ApartmentListing] = []
    seen_links: set[str] = set()

    for card in cards:
        try:
            listing = _parse_card(
                card,
                neigh,
                price_min,
                price_max,
                move_in_from,
                seen_links,
                fallback_start + len(listings),
            )
            if listing:
                listings.append(listing)
        except Exception:
            continue

    return listings


def _scrape_homegate_page(
    page,
    current_url: str,
    neigh: str,
    page_num: int,
    price_min: int,
    price_max: int,
    move_in_from: Optional[date],
    fallback_start: int,
) -> List[ApartmentListing]:
    try:
        page.goto(current_url, wait_until="domcontentloaded", timeout=90000)
        _dismiss_consent(page)
        _wait_for_results(page)
        _scroll_results(page)

        cards = _find_result_cards(page)
        logger.info(f"Homegate {neigh} page {page_num}: found {len(cards)} cards")
        listings = _parse_cards(
            cards,
            neigh,
            price_min,
            price_max,
            move_in_from,
            fallback_start,
        )
        logger.info(f"Homegate {neigh} page {page_num}: Added {len(listings)} listings")
        return listings
    except Exception as e:
        logger.error(f"Homegate {neigh} page {page_num} failed: {e}")
        return []


def _scrape_homegate_neighborhood(
    page,
    neigh: str,
    price_min: int,
    price_max: int,
    move_in_from: Optional[date],
    max_pages: int,
    fallback_start: int,
) -> List[ApartmentListing]:
    url = _build_homegate_url(neigh, price_min, price_max)
    logger.info(f"Scraping Homegate → {neigh} | URL: {url}")

    listings: List[ApartmentListing] = []
    for page_num in range(1, max_pages + 1):
        current_url = f"{url}&ep={page_num}" if page_num > 1 else url
        page_listings = _scrape_homegate_page(
            page,
            current_url,
            neigh,
            page_num,
            price_min,
            price_max,
            move_in_from,
            fallback_start + len(listings),
        )
        listings.extend(page_listings)

    return listings


def scrape_homegate(
    price_min: int = 1700,
    price_max: int = 3000,
    neighborhoods: Optional[List[str]] = None,
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
    from ..locations import default_zurich_quartiers

    if neighborhoods is None:
        neighborhoods = default_zurich_quartiers()

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
            results.extend(
                _scrape_homegate_neighborhood(
                    page,
                    neigh,
                    price_min,
                    price_max,
                    move_in_from,
                    max_pages,
                    len(results),
                )
            )

        browser.close()

    logger.info(f"Homegate scraper finished. Total: {len(results)} listings")
    return results
