"""
Search service: the shared core used by both the CLI and the REST API.

Wraps scraping (`run_all_scrapers`) and filtering (`apply_filters`) behind a
single function so the two front-ends stay in sync.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from .filters import apply_filters
from .locations import default_metro_search, default_zurich_quartiers
from .logger import logger
from .models import ApartmentListing
from .scrapers import normalize_sources, run_all_scrapers


def resolve_neighborhoods(neighborhoods: Optional[List[str]], metro: bool) -> List[str]:
    """
    Resolve the effective list of locations to search.

    Explicit neighborhoods win; otherwise fall back to the whole metro region
    (when ``metro`` is True) or the city quartiers.
    """
    if neighborhoods:
        return list(neighborhoods)
    return default_metro_search() if metro else default_zurich_quartiers()


def search_apartments(
    *,
    price_min: int = 1700,
    price_max: int = 3000,
    move_in_from: Optional[date] = None,
    neighborhoods: Optional[List[str]] = None,
    metro: bool = False,
    only_flexible: bool = True,
    max_pages: int = 5,
    sources: Optional[List[str]] = None,
) -> List[ApartmentListing]:
    """
    Run a full apartment search: scrape the selected sources, then filter.

    Parameters mirror the CLI options. ``sources`` is validated (unknown names
    raise ValueError); None/empty means all sources. Returns the filtered,
    deduplicated, price-sorted listings.
    """
    selected_sources = normalize_sources(sources)
    locations = resolve_neighborhoods(neighborhoods, metro)

    logger.info(
        "Service search | price=%s-%s | move_in=%s | locations=%s | "
        "sources=%s | only_flexible=%s | max_pages=%s",
        price_min,
        price_max,
        move_in_from,
        locations,
        selected_sources,
        only_flexible,
        max_pages,
    )

    raw_listings = run_all_scrapers(
        price_min=price_min,
        price_max=price_max,
        neighborhoods=locations,
        move_in_from=move_in_from,
        max_pages=max_pages,
        sources=selected_sources,
    )

    return (
        apply_filters(
            listings=raw_listings,
            price_min=price_min,
            price_max=price_max,
            move_in_from=move_in_from,
            neighborhoods=locations,
            only_month_to_month=only_flexible,
        )
        or []
    )
