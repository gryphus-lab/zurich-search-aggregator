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

# Preferred result-card selectors, tried in order. The last is a resilient
# fallback: any anchor pointing at a listing-detail URL.
_CARD_SELECTORS = (
    "[data-test='result-list-item']",
    "article[data-test='result-item']",
    "div[data-test='listing-card']",
    "a[href*='/rent/'][href*='-']",
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

    Homegate shows a OneTrust banner on first load that overlays the page and
    can block the result list from rendering. Clicking "accept all"
    (#onetrust-accept-btn-handler / #accept-recommended-btn-handler) lets the
    results load. Best-effort: ignore if the banner isn't shown.
    """
    for selector in (
        "#onetrust-accept-btn-handler",
        "#accept-recommended-btn-handler",
        "button[aria-label*='accept' i]",
    ):
        try:
            btn = page.locator(selector).first
            if btn.count() > 0 and btn.is_visible():
                btn.click(timeout=3000)
                page.wait_for_timeout(500)
                return
        except Exception:
            continue


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
            # Homegate search URL. City quartiers use the district path; metro
            # municipalities (not Zurich-city districts) use free-text location
            # search. "apartment" (not "furnished-dwelling") so all apartment
            # types are returned.
            url = _build_homegate_url(neigh, price_min, price_max)

            logger.info(f"Scraping Homegate → {neigh} | URL: {url}")

            for page_num in range(1, max_pages + 1):
                current_url = f"{url}&ep={page_num}" if page_num > 1 else url

                try:
                    page.goto(current_url, wait_until="domcontentloaded", timeout=90000)

                    # Accept the OneTrust cookie banner so the result list renders.
                    _dismiss_consent(page)

                    # Wait for the result list to appear (don't just sleep blindly).
                    try:
                        page.wait_for_selector(
                            "[data-test='result-list-item']", timeout=15000
                        )
                    except Exception:
                        page.wait_for_timeout(4000)

                    # Scroll to trigger lazy-loaded result cards.
                    for _ in range(4):
                        page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                        page.wait_for_timeout(1500)

                    cards = _find_result_cards(page)
                    logger.info(
                        f"Homegate {neigh} page {page_num}: found {len(cards)} cards"
                    )

                    added = 0
                    seen_links: set[str] = set()
                    for card in cards:
                        try:
                            text = card.inner_text().strip()
                            if len(text) < 40:
                                continue

                            href = _card_href(card)
                            link = (
                                "https://www.homegate.ch" + href
                                if href.startswith("/")
                                else href
                            )
                            if not link or link in seen_links:
                                continue
                            seen_links.add(link)

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

                            # Title / rooms. Homegate renders e.g. "3.5\nrooms"
                            # (English) or "3½ Zimmer" (German); allow whitespace
                            # (incl. a newline) between the count and the word.
                            room_match = re.search(
                                r"(\d+(?:[.,]\d+)?|\d+\s*½|\d+\s*1/2)\s*(rooms?|zimmer)",
                                text,
                                re.I,
                            )
                            if room_match:
                                count = room_match.group(1).replace("\n", " ").strip()
                                title = f"{count} {room_match.group(2).lower()}"
                            else:
                                title = "Apartment"

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
                            normalized_href = href.rstrip("/") if href else ""
                            listing_id = (
                                normalized_href.split("/")[-1]
                                if normalized_href
                                else ""
                            )
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
                            # Tenancy tagging ([FLEXIBLE]/[STANDARD]) is applied
                            # centrally in apply_filters, not here, to avoid
                            # double-prefixing the description_snippet.
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
