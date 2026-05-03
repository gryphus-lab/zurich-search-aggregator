import re
from datetime import date, datetime
from calendar import monthrange
from typing import List, Optional

from playwright.sync_api import sync_playwright

from ..models import ApartmentListing
from ..logger import logger


def get_checkout_one_year_later(start_date: date) -> date:
    """2026-05-01 → 2027-04-30"""
    next_year = start_date.year + 1
    next_month = start_date.month - 1 if start_date.month > 1 else 12

    # Get the last day of next month
    _, last_day = monthrange(next_year, next_month)
    return date(next_year, next_month, last_day)


def parse_available_from(avail_str: Optional[str]) -> Optional[date]:
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
) -> Optional[ApartmentListing]:
    text = (text or "").strip()

    title_match = re.search(r"#(\d+)\s*•\s*(\S.*$)", text)
    title = title_match.group(1) if title_match else "Blueground Apartment"
    logger.info(f"Title: {title}")

    size_match = re.search(r"(\d+\s*m²*.$)", text)
    size_m2 = float(size_match.group(1)) if size_match else None
    logger.info(f"Size: {size_m2}")

    address_match = re.search(r"#\d+\s*•\s*(.+?)(?:\n|$)", text)
    address = address_match.group(1).strip() if address_match else neighborhood
    logger.info(f"Address: {address}")

    available_from = move_in_from
    logger.info(f"Available from: {available_from}")

    price_match = re.search(r"^.*CHF(.*$)", text)
    price_str = (
        price_match.group(1).replace("’", "").replace("'", "").replace(",", "").strip()
    )
    if price_str:
        price = float(price_str)
    else:
        price = None

    logger.info(f"For address: {address}, price: {price}")

    # if move_in_from and available_from and available_from < move_in_from:
    #     return None

    listing = ApartmentListing(
        id=title,
        title=f"{title} • {address}",
        price_chf=price,
        neighborhood=neighborhood,
        address=address,
        link="https://www.theblueground.com/p/furnished-apartments/zrh-" + title,
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

                        # # More robust link extraction - try multiple strategies
                        # link = None
                        # # Strategy 1: Specific href
                        # link_elem = card.locator(
                        #     "a[href*='/furnished-apartments/zrh']"
                        # ).first
                        # if link_elem.count() > 0:
                        #     href = link_elem.get_attribute("href")
                        #     if href:
                        #         link = (
                        #             "https://www.theblueground.com" + href
                        #             if href.startswith("/")
                        #             else href
                        #         )

                        # # Strategy 2: Any link inside the card
                        # if not link:
                        #     any_link = card.locator("a").first
                        #     if any_link.count() > 0:
                        #         href = any_link.get_attribute("href")
                        #         if href and "/furnished-apartments" in href:
                        #             link = (
                        #                 "https://www.theblueground.com" + href
                        #                 if href.startswith("/")
                        #                 else href
                        #             )

                        # if not link:
                        #     continue

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
