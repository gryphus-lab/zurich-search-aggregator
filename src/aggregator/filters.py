from datetime import date
from typing import List, Optional
import hashlib

from .models import ApartmentListing
from .logger import logger  # standard logger


def normalize_neighborhood(neigh: str) -> str:
    """
    Normalize a neighborhood string to a canonical neighborhood name.

    Maps known variants (for example, "oerlikon zürich" or "quartier oerlikon") to a canonical form and returns the mapped value; if no mapping exists, returns the input title-cased.

    Parameters:
        neigh (str): Neighborhood string to normalize; may include variants, punctuation, or leading "quartier-".

    Returns:
        str: Canonical neighborhood name when recognized (e.g., "Oerlikon"), otherwise the input with title casing.
    """
    mapping = {
        "oerlikon": "Oerlikon",
        "seebach": "Seebach",
        "wipkingen": "Wipkingen",
        "altstetten": "Altstetten",
        "oerlikon zürich": "Oerlikon",
        "quartier oerlikon": "Oerlikon",
    }
    key = (
        neigh.lower()
        .strip()
        .replace(" ", "-")
        .replace("quartier-", "")
        .replace("zürich", "")
        .rstrip("-")
    )
    return mapping.get(key, neigh.title())


def is_month_to_month_friendly(listing: ApartmentListing) -> bool:
    """
    Detect whether a listing advertises flexible, temporary, or furnished tenancy.

    Performs a case-insensitive substring check of the listing's description and raw data for common flexibility/service/furnishing keywords.

    Returns:
        True if any flexibility/service/furnishing keyword is found, False otherwise.
    """
    text = (listing.description_snippet or "").lower() + str(listing.raw_data).lower()
    keywords = [
        "befristet",
        "temporary",
        "kurzfristig",
        "month to month",
        "monthly",
        "flexible",
        "möbliert",
        "furnished",
        "serviced",
        "sublet",
        "priority rental",
        "add your move-in date",
    ]
    return any(kw in text for kw in keywords)


def generate_unique_id(listing: ApartmentListing) -> str:
    """
    Produce a deterministic 16-hex-character identifier for a listing derived from its link and whole-CHF price.

    Parameters:
        listing (ApartmentListing): Listing whose `link` and `price_chf` (rounded to no decimal places) are used to compute the identifier.

    Returns:
        str: A 16-character hexadecimal string (first 16 chars of the MD5 hash of the derived key).
    """
    key = f"{listing.link}|{listing.price_chf:.0f}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()[:16]


def apply_filters(
    listings: List[ApartmentListing],
    price_min: int,
    price_max: int,
    move_in_from: Optional[date] = None,
    neighborhoods: Optional[List[str]] = None,
    only_month_to_month: bool = False,  # Changed default to False temporarily
) -> List[ApartmentListing]:
    """
    Apply a set of filters to apartment listings and return the filtered, deduplicated, and sorted results.

    Filters applied: price range, normalized neighborhood membership, optional earliest move-in date, and optional month-to-month friendliness. Listings are deduplicated using a deterministic ID derived from the listing and sorted by ascending price then by availability date.

    Parameters:
        listings (List[ApartmentListing]): Input apartment listings to filter.
        price_min (int): Minimum acceptable price (inclusive).
        price_max (int): Maximum acceptable price (inclusive).
        move_in_from (Optional[date]): If provided, exclude listings whose available_from is earlier than this date.
        neighborhoods (Optional[List[str]]): If provided, only listings whose normalized neighborhood is in this list are kept.
            If `None`, a default set of neighborhoods is used.
        only_month_to_month (bool): If True, only listings classified as month-to-month friendly are retained; when False,
            both types are retained but listings are annotated.

    Returns:
        List[ApartmentListing]: Filtered, deduplicated, and sorted listings.

    Notes:
        - This function mutates each kept listing's `description_snippet` by prefixing it with either "[FLEXIBLE] " or "[STANDARD] ".
        - Deduplication uses a deterministic 16-character MD5-based ID derived from the listing (e.g., link and rounded price).
    """
    logger.info(
        f"Applying filters to {len(listings)} listings | Price: {price_min}-{price_max} CHF | Move-in from: {move_in_from} | Neighborhoods: {neighborhoods} | Only month-to-month: {only_month_to_month}"
    )
    if not listings:
        return []

    if neighborhoods is None:
        neighborhoods = ["Oerlikon", "Seebach", "Wipkingen", "Altstetten"]

    normalized_neighs = {normalize_neighborhood(n) for n in neighborhoods}
    seen = set()
    filtered: List[ApartmentListing] = []

    for apt in listings:
        # 1. Price filter
        if not (price_min <= apt.price_chf <= price_max):
            continue

        # 2. Neighborhood filter (more forgiving)
        norm_neigh = normalize_neighborhood(apt.neighborhood)
        if normalized_neighs and norm_neigh not in normalized_neighs:
            continue

        # 3. Move-in date filter
        if move_in_from and apt.available_from and apt.available_from < move_in_from:
            continue

        # 4. Flexible marking (don't filter out — just mark)
        flexible = is_month_to_month_friendly(apt)
        if only_month_to_month and not flexible:
            continue

        apt.description_snippet = (
            "[FLEXIBLE] " + (apt.description_snippet or "")
            if flexible
            else "[STANDARD] " + (apt.description_snippet or "")
        )

        # 5. Deduplication
        uid = generate_unique_id(apt)
        if uid in seen:
            continue
        seen.add(uid)

        filtered.append(apt)

    # Sort by price ascending
    filtered.sort(key=lambda x: (x.price_chf, x.available_from or date.max))
    logger.info(f"After filtering: {len(filtered)} listings remain")
    return filtered
