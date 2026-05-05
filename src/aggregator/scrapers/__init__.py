from .blueground import scrape_blueground
from .flatfox import scrape_flatfox
from .homegate import scrape_homegate
from .ums import scrape_ums
from typing import List, Optional
from datetime import date

from ..models import ApartmentListing
from ..logger import logger  # standard logger


def run_all_scrapers(
    price_min: int,
    price_max: int,
    neighborhoods: List[str],
    move_in_from: Optional[date] = None,
    max_pages: int = 5,
) -> List[ApartmentListing]:
    """
    Aggregate apartment listings collected from all active scrapers using the given filters.

    Parameters:
        price_min (int): Minimum price filter.
        price_max (int): Maximum price filter.
        neighborhoods (List[str]): Neighborhood names or identifiers to filter listings.
        move_in_from (Optional[date]): Earliest acceptable move-in date; if None, no move-in date filter is applied.
        max_pages (int): Maximum pages to fetch for scrapers that support pagination (applies to Flatfox).

    Returns:
        List[ApartmentListing]: Combined listings returned by scrapers that completed successfully.
    """
    logger.info("Run all active scrapers with parameters:s")
    all_listings: List[ApartmentListing] = []

    try:
        flatfox_results = scrape_flatfox(
            price_min=price_min,
            price_max=price_max,
            neighborhoods=neighborhoods,
            move_in_from=move_in_from,
            max_pages=max_pages,
        )
        all_listings.extend(flatfox_results)
        logger.info(f"Flatfox → added {len(flatfox_results)} listings")
    except Exception as e:
        logger.error(f"Flatfox error: {e}")

    try:
        blueground_results = scrape_blueground(
            price_min=price_min,
            price_max=price_max,
            neighborhoods=neighborhoods,
            move_in_from=move_in_from,
        )
        all_listings.extend(blueground_results)
        logger.info(f"Blueground → added {len(blueground_results)} listings")
    except Exception as e:
        logger.error(f"Blueground error: {e}")

    try:
        homegate_results = scrape_homegate(
            price_min=price_min,
            price_max=price_max,
            neighborhoods=neighborhoods,
            move_in_from=move_in_from,
            max_pages=max_pages,
        )
        all_listings.extend(homegate_results)
        logger.info(f"Homegate → added {len(homegate_results)} listings")
    except Exception as e:
        logger.error(f"Homegate error: {e}")

    try:
        ums_results = scrape_ums(
            price_min=price_min,
            price_max=price_max,
            neighborhoods=neighborhoods,
            move_in_from=move_in_from,
        )
        all_listings.extend(ums_results)
        logger.info(f"UMS → added {len(ums_results)} listings")
    except Exception as e:
        logger.error(f"UMS error: {e}")

    return all_listings
