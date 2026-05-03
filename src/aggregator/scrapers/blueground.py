import re
from datetime import date, datetime
from calendar import monthrange
from typing import List, Optional

from playwright.sync_api import sync_playwright

from ..models import ApartmentListing
from ..logger import logger


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


def parse_available_from(avail_str: Optional[str]) -> Optional[date]:
    """
    Parse an "available from" string into a date.

    Strips a leading "Available" (case-insensitive) and attempts to parse the remaining text using several common date formats.

    Parameters:
        avail_str (Optional[str]): Input string possibly prefixed with "Available" and containing a date (e.g. "Available 1 Jan 2024").

    Returns:
        Optional[date]: The parsed `date` if parsing succeeds, `None` if the input is falsy or no supported format matches.

    Accepted date formats:
        - "%d %b %Y" (e.g. "1 Jan 2024")
        - "%b %d %Y" (e.g. "Jan 1 2024")
        - "%d %B %Y" (e.g. "1 January 2024")
        - "%d.%m.%Y" (e.g. "01.01.2024")
    """
    if not avail_str:
        return None
    avail_str = re.sub(r"Available\s*", "", avail_str, flags=re.I).strip()
    for fmt in ("%d %b %Y", "%b %d %Y", "%d %B %Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(avail_str, fmt).date()
        except ValueError:
            continue
    return None


def parse_blueground_card(
    *,
    text: str,
    neighborhood: str,
    move_in_from: Optional[date] = None,
    link: Optional[str] = None,
) -> Optional[ApartmentListing]:
    """
    Parse a Blueground listing card's raw text and construct an ApartmentListing populated with extracted fields.

    Parameters:
        text (str): Raw inner-text of the card element to parse.
        neighborhood (str): Neighborhood used as a fallback for address when one cannot be extracted.
        move_in_from (Optional[date]): Optional move-in date to filter listings. If provided with a link, reject if parsed available_from is earlier (apartment would be rented out by move-in date). Returns None in that case.
        link (Optional[str]): Optional link to the listing; if not provided, one is generated from title. The ID is extracted from the last path segment of the link.

    Returns:
        Optional[ApartmentListing]: An ApartmentListing populated with id, title, address, price_chf, neighborhood,
        link, available_from, size_m2, rooms (None), source ("blueground"), furnished (True), a short description_snippet,
        and raw_data. Returns `None` only if a listing cannot be produced from the provided text or if move_in_from conflicts with parsed availability.
    """
    text = (text or "").strip()

    # Extract title from "#N" pattern - could have room type before it
    title_match = re.search(r"^(.*)#(\d+)", text, re.MULTILINE)
    if title_match:
        room_type = title_match.group(1).strip().rstrip("•").strip()
        apt_id = title_match.group(2)
        title = f"{room_type} • #{apt_id}" if room_type else apt_id
    else:
        title = "Blueground Apartment"
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
    if title == "Blueground Apartment":
        final_title = "Blueground Apartment"
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
                for i in range(8):
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
