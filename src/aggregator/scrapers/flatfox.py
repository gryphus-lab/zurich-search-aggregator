import re
from datetime import date, datetime
from typing import List, Optional

from playwright.sync_api import sync_playwright

from ..models import ApartmentListing
from ..logger import logger  # standard logger


def parse_available_from(avail_str: Optional[str]) -> Optional[date]:
    if not avail_str:
        return None
    avail_str = re.sub(
        r"(?:ab|from|sofort|verfügbar ab|available from?)\s*", "", avail_str, flags=re.I
    ).strip()
    for fmt in ("%d.%m.%Y", "%d %B %Y", "%d %b %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(avail_str, fmt).date()
        except ValueError:
            continue
    return None


def parse_flatfox_card(
    *,
    text: str,
    link: str,
    neighborhood: str,
    move_in_from: Optional[date] = None,
) -> Optional[ApartmentListing]:
    """
    Parse a single Flatfox listing card.

    Kept separate from Playwright so we can unit test parsing logic.
    """
    text = (text or "").strip()
    if len(text) < 30 or not link:
        return None

    # Improved price regex - handles 1’950, 2'130, CHF 1,950 etc.
    price_match = re.search(r"(?:CHF\s*)?([\d’',]+)", text)
    if not price_match:
        return None
    price_str = (
        price_match.group(1).replace("’", "").replace("'", "").replace(",", "").strip()
    )
    price = float(price_str)

    # Title / rooms
    room_match = re.search(r"(\d+(?:\s*[½1/2])?\s*(?:rooms?|zimmer))", text, re.I)
    title = (
        room_match.group(0).strip() if room_match else f"Apartment in {neighborhood}"
    )

    # Available from
    avail_match = re.search(
        r"(?:ab|verfügbar|available|from)\s*([\d.]{8,10}|\d{1,2}\s*[A-Za-z]+\s*\d{4})",
        text,
        re.I,
    )
    avail_str = avail_match.group(1) if avail_match else None
    available_from = parse_available_from(avail_str)

    if move_in_from and available_from and available_from < move_in_from:
        return None

    # Size
    size_match = re.search(r"(\d+)\s*m²", text)
    size_m2 = float(size_match.group(1)) if size_match else None

    listing = ApartmentListing(
        id=link.split("/")[-1] if link else "ff-unknown",
        title=title,
        price_chf=price,
        neighborhood=neighborhood,
        address=neighborhood,
        link=link,
        available_from=available_from,
        size_m2=size_m2,
        rooms=None,
        source="flatfox",
        furnished=True,
        description_snippet=text[:500],
        raw_data={"raw_text": text},
    )

    # Mark flexible
    lower = text.lower()
    if any(
        k in lower
        for k in [
            "temporary",
            "befristet",
            "kurzfristig",
            "sublet",
            "möbliert",
            "furnished",
        ]
    ):
        listing.description_snippet = "[FLEXIBLE] " + listing.description_snippet

    return listing


def scrape_flatfox(
    price_min: int = 1700,
    price_max: int = 3000,
    neighborhoods: List[str] = None,
    move_in_from: Optional[date] = None,
    max_pages: int = 5,
) -> List[ApartmentListing]:
    if neighborhoods is None:
        neighborhoods = ["Oerlikon", "Seebach", "Wipkingen", "Altstetten"]

    results: List[ApartmentListing] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 1100},
        )
        page = context.new_page()

        for neigh in neighborhoods:
            base_url = (
                f"https://flatfox.ch/en/search/"
                f"?query={neigh}+Zürich"
                f"&offer_type=RENT"
                f"&object_category=APARTMENT"
                f"&min_price={price_min}"
                f"&max_price={price_max}"
                f"&is_furnished=true"
            )

            logger.info(
                f"Scraping Flatfox → {neigh} | {price_min}-{price_max} CHF (furnished)"
            )

            for page_num in range(1, max_pages + 1):
                url = f"{base_url}&page={page_num}" if page_num > 1 else base_url

                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=120000)
                    page.wait_for_timeout(15000)  # give Flatfox extra time

                    # Aggressive scrolling
                    for _ in range(6):
                        page.evaluate("window.scrollBy(0, 1800)")
                        page.wait_for_timeout(3000)

                    cards = page.locator("a[href*='/flat/']").all()

                    added = 0
                    for card in cards:
                        try:
                            text = card.inner_text().strip()

                            href = card.get_attribute("href") or ""
                            link = (
                                "https://flatfox.ch" + href
                                if href.startswith("/")
                                else href
                            )
                            if not link or "/flat/" not in link:
                                continue

                            listing = parse_flatfox_card(
                                text=text,
                                link=link,
                                neighborhood=neigh,
                                move_in_from=move_in_from,
                            )
                            if listing is None:
                                continue

                            if (
                                listing.price_chf < price_min
                                or listing.price_chf > price_max
                            ):
                                continue

                            results.append(listing)
                            added += 1

                        except Exception:
                            continue

                    logger.info(
                        f"  Page {page_num}: Found {len(cards)} cards → added {added} listings (total {len(results)})"
                    )

                except Exception as e:
                    logger.error(f"  Error on {neigh} page {page_num}: {e}")
                    continue

        browser.close()

    return results
