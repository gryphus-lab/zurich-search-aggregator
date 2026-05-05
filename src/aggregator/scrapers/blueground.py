import re
from datetime import date
from calendar import monthrange
from typing import List, Optional
from ..utils import parse_available_from

from playwright.sync_api import sync_playwright

from ..models import ApartmentListing
from ..logger import logger

BLUEGROUND_TITLE = "Blueground Apartment"


def get_checkout_one_year_later(start_date: date) -> date:
    """
    Computes the checkout date one year after `start_date`, using the last day of the month immediately before `start_date.month` in the following year.

    Parameters:
        start_date (date): Reference start date.

    Returns:
        date: Last day of the month preceding `start_date.month` in the year `start_date.year + 1` (e.g., 2026-05-01 -> 2027-04-30).
    """
    next_year = start_date.year + 1
    next_month = start_date.month - 1 if start_date.month > 1 else 12

    # Get the last day of next month
    _, last_day = monthrange(next_year, next_month)
    return date(next_year, next_month, last_day)


def parse_blueground_card(
    *,
    text: str,
    neighborhood: str,
    move_in_from: Optional[date] = None,
    link: Optional[str] = None,
) -> Optional[ApartmentListing]:
    """
    Parse a Blueground listing card's inner text into an ApartmentListing.
    
    Parses a raw card text produced by the Blueground listing UI and constructs an ApartmentListing with extracted id, title, address, price (CHF), neighborhood, link, availability date, size (m²), and other metadata.
    
    Parameters:
        text (str): Raw inner text of the card element to parse; may be empty or whitespace.
        neighborhood (str): Fallback neighborhood/address used when an address cannot be extracted from the text.
        move_in_from (Optional[date]): When provided, this date will override the parsed availability date for the returned listing. Additionally, if `link` is provided and the parsed "available from" date exists and is earlier than `move_in_from`, the listing is rejected and the function returns `None`.
        link (Optional[str]): Optional listing URL; when present the listing id is taken from the last path segment of this URL. When omitted, a canonical Blueground URL is generated from the extracted id or title.
    
    Returns:
        Optional[ApartmentListing]: An ApartmentListing populated with parsed fields (id, title, address, price_chf, neighborhood, link, available_from, size_m2, rooms=None, source="blueground", furnished=True, description_snippet, raw_data). Returns `None` only when `move_in_from` and `link` are provided and the parsed availability date is earlier than `move_in_from`.
    """
    text = (text or "").strip()

    # Extract title from "#N" pattern - could have room type before it
    title_match = re.search(r"^(.*)#(\d+)", text, re.MULTILINE)
    if title_match:
        room_type = title_match.group(1).strip().rstrip("•").strip()
        apt_id = title_match.group(2)
        title = f"{room_type} • #{apt_id}" if room_type else apt_id
    else:
        title = BLUEGROUND_TITLE
        apt_id = None
    logger.info(f"Title: {title}")

    size_match = re.search(r"(\d+)\s*m²", text)
    size_m2 = float(size_match.group(1)) if size_match else None
    logger.info(f"Size: {size_m2}")

    address_match = re.search(r"#\d+\s*•\s*(.+?)(?:\n|$)", text)
    address = address_match.group(1).strip() if address_match else neighborhood
    logger.info(f"Address: {address}")

    # Parse available_from from text
    available_match = re.search(r"Available\s+(.+?)(?:\n|$)", text, re.I)
    available_from_text = available_match.group(1).strip() if available_match else None
    parsed_available_from = parse_available_from(available_from_text)
    logger.info(f"Parsed available from: {parsed_available_from}")

    # If move_in_from provided AND link was provided, reject if parsed date is earlier than move_in
    if (
        move_in_from
        and link
        and parsed_available_from
        and parsed_available_from < move_in_from
    ):
        logger.info(
            f"Rejecting: parsed date {parsed_available_from} is earlier than move_in_from {move_in_from} (with link filtering)"
        )
        return None

    # Use move_in_from if provided, else use parsed available_from
    available_from = move_in_from if move_in_from else parsed_available_from
    logger.info(f"Available from: {available_from}")

    price_match = re.search(r"^.*CHF(.*$)", text, re.MULTILINE)
    price_str = (
        price_match.group(1).replace("'", "").replace("'", "").replace(",", "").strip()
        if price_match
        else ""
    )
    if price_str:
        try:
            price = float(price_str)
        except ValueError:
            price = 0.0
    else:
        price = 0.0

    logger.info(f"For address: {address}, price: {price}")

    # Extract ID from link or use apt_id or title
    if link:
        link_id = link.rsplit("/", 1)[-1] or title
    else:
        link_id = apt_id if apt_id else title
        link = f"https://www.theblueground.com/p/furnished-apartments/zrh-{link_id}"

    # Build title: if default "Blueground Apartment" was used, use as-is; otherwise format as "title • address"
    if title == BLUEGROUND_TITLE:
        final_title = BLUEGROUND_TITLE
    else:
        final_title = f"{title} • {address}"

    listing = ApartmentListing(
        id=link_id,
        title=final_title,
        price_chf=price,
        neighborhood=neighborhood,
        address=address,
        link=link,
        available_from=available_from,
        size_m2=size_m2,
        rooms=None,
        source="blueground",
        furnished=True,
        description_snippet=f"Add dates to see price | {text[:450]}",
        raw_data={"raw_text": text},
    )

    return listing


def scrape_blueground(
    price_min: int = 1700,
    price_max: int = 3000,
    neighborhoods: List[str] = None,
    move_in_from: Optional[date] = None,
) -> List[ApartmentListing]:
    """
    Scrape apartment listings from Blueground for the given neighborhoods and optional move-in date.

    Parameters:
        price_min (int): Minimum price shown in logs; not used to filter results.
        price_max (int): Maximum price shown in logs; not used to filter results.
        neighborhoods (List[str] | None): List of neighborhood names to scrape. Defaults to a predefined set when None.
        move_in_from (date | None): Optional move-in date used to request availability date range on the site.

    Returns:
        List[ApartmentListing]: Collected apartment listings parsed from Blueground cards.
    """
    if neighborhoods is None:
        neighborhoods = ["Oerlikon", "Seebach", "Wipkingen", "Altstetten"]

    slug_map = {
        "Oerlikon": "oerlikon",
        "Seebach": "seebach",
        "Wipkingen": "wipkingen",
        "Altstetten": "altstetten",
    }

    results: List[ApartmentListing] = []

    logger.info(
        f"Starting Blueground scrape | Price: {price_min}-{price_max} | Move-in: {move_in_from or 'Any'}"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 1100},
        )
        page = context.new_page()

        for neigh in neighborhoods:
            slug = slug_map.get(neigh)
            if not slug:
                logger.warning(f"No slug mapping for {neigh}")
                continue

            url = (
                f"https://www.theblueground.com/furnished-apartments-zurich-ch/s/{slug}"
            )
            if move_in_from:
                check_in = move_in_from.strftime("%Y-%m-%d")
                check_out = get_checkout_one_year_later(move_in_from).strftime(
                    "%Y-%m-%d"
                )
                url += f"?checkIn={check_in}&checkOut={check_out}&totalMonthly=true"
                logger.info(
                    f"Using date range → checkIn={check_in} & checkOut={check_out}"
                )

            logger.info(f"Navigating to Blueground → {neigh} | URL: {url}")

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=90000)
                page.wait_for_timeout(10000)

                # Scrolling
                logger.debug("Starting scrolling...")
                last_height = page.evaluate("document.body.scrollHeight")
                for _ in range(8):
                    page.evaluate("window.scrollBy(0, 1800)")
                    page.wait_for_timeout(3500)
                    new_height = page.evaluate("document.body.scrollHeight")
                    if new_height == last_height:
                        break
                    last_height = new_height

                # Get all potential cards
                cards = page.locator(
                    "article, div[class*='card'], div[class*='property'], div[class*='listing'], div[class*='apartment']"
                ).all()

                logger.info(f"Found {len(cards)} potential cards for {neigh}")

                added = 0
                for idx, card in enumerate(cards):
                    try:
                        text = card.inner_text().strip()
                        if len(text) < 30:
                            continue

                        listing = parse_blueground_card(
                            text=text,
                            neighborhood=neigh,
                            move_in_from=move_in_from,
                        )
                        if listing is None:
                            continue

                        results.append(listing)
                        added += 1

                        logger.info(f"Added listing #{added}: {listing.title}")

                    except Exception as e:
                        logger.error(f"Card {idx} parsing failed: {e}")
                        continue

                logger.info(
                    f"Blueground {neigh}: Added {added} listings (total {len(results)})"
                )

            except Exception as e:
                logger.error(f"Blueground {neigh} scrape failed: {e}", exc_info=True)

        browser.close()

    logger.info(f"Blueground finished. Total listings: {len(results)}")
    return results
