from .blueground import scrape_blueground
from .flatfox import scrape_flatfox
from .homegate import scrape_homegate
from .ums import scrape_ums
from typing import List, Optional
from datetime import date

from ..models import ApartmentListing
from ..logger import logger  # standard logger


# Canonical ordering of sources. Iteration order here defines the order in
# which scrapers run and in which their listings are concatenated.
AVAILABLE_SOURCES: List[str] = ["flatfox", "blueground", "homegate", "ums"]


def _call_flatfox(price_min, price_max, neighborhoods, move_in_from, max_pages):
    return scrape_flatfox(
        price_min=price_min,
        price_max=price_max,
        neighborhoods=neighborhoods,
        move_in_from=move_in_from,
        max_pages=max_pages,
    )


def _call_blueground(price_min, price_max, neighborhoods, move_in_from, max_pages):
    return scrape_blueground(
        price_min=price_min,
        price_max=price_max,
        neighborhoods=neighborhoods,
        move_in_from=move_in_from,
    )


def _call_homegate(price_min, price_max, neighborhoods, move_in_from, max_pages):
    return scrape_homegate(
        price_min=price_min,
        price_max=price_max,
        neighborhoods=neighborhoods,
        move_in_from=move_in_from,
        max_pages=max_pages,
    )


def _call_ums(price_min, price_max, neighborhoods, move_in_from, max_pages):
    return scrape_ums(
        price_min=price_min,
        price_max=price_max,
        neighborhoods=neighborhoods,
        move_in_from=move_in_from,
    )


# Source name -> adapter that calls the underlying scraper with the args it
# accepts. Keep keys in sync with AVAILABLE_SOURCES.
_SCRAPER_DISPATCH = {
    "flatfox": _call_flatfox,
    "blueground": _call_blueground,
    "homegate": _call_homegate,
    "ums": _call_ums,
}


def normalize_sources(sources: Optional[List[str]]) -> List[str]:
    """
    Resolve a user-supplied source selection to a validated, ordered list.

    Parameters:
        sources (Optional[List[str]]): Requested source names (any case). When
            None or empty, all available sources are selected.

    Returns:
        List[str]: Known source names in canonical order, de-duplicated.

    Raises:
        ValueError: If any requested name is not a known source.
    """
    if not sources:
        return list(AVAILABLE_SOURCES)

    requested = {s.strip().lower() for s in sources if s and s.strip()}
    unknown = requested - set(AVAILABLE_SOURCES)
    if unknown:
        raise ValueError(
            f"Unknown source(s): {', '.join(sorted(unknown))}. "
            f"Available: {', '.join(AVAILABLE_SOURCES)}"
        )
    # Preserve canonical order regardless of the order the user listed them.
    return [s for s in AVAILABLE_SOURCES if s in requested]


def run_all_scrapers(
    price_min: int,
    price_max: int,
    neighborhoods: List[str],
    move_in_from: Optional[date] = None,
    max_pages: int = 5,
    sources: Optional[List[str]] = None,
) -> List[ApartmentListing]:
    """
    Collect apartment listings from the selected scrapers using the provided filters.

    Parameters:
        price_min (int): Minimum price filter.
        price_max (int): Maximum price filter.
        neighborhoods (List[str]): Neighborhood names or identifiers to search.
        move_in_from (Optional[date]): Earliest acceptable move-in date; if None, no move-in date filter is applied.
        max_pages (int): Maximum pages to fetch for scrapers that support pagination (Flatfox, Homegate).
        sources (Optional[List[str]]): Which sources to run (any of
            ``flatfox``, ``blueground``, ``homegate``, ``ums``). When None or
            empty, all sources run. Unknown names raise ValueError.

    Returns:
        List[ApartmentListing]: Combined listings from the scrapers that completed successfully.
    """
    selected = normalize_sources(sources)
    logger.info(f"Running scrapers: {', '.join(selected)}")
    all_listings: List[ApartmentListing] = []

    for name in selected:
        try:
            results = _SCRAPER_DISPATCH[name](
                price_min, price_max, neighborhoods, move_in_from, max_pages
            )
            all_listings.extend(results)
            logger.info(f"{name.capitalize()} → added {len(results)} listings")
        except Exception as e:
            logger.error(f"{name.capitalize()} error: {e}")

    return all_listings
