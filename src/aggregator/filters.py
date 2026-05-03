from datetime import date
from typing import List, Optional
import hashlib

from .models import ApartmentListing
from .logger import logger  # standard logger


def normalize_neighborhood(neigh: str) -> str:
    """Make neighborhood matching more robust"""
    mapping = {
        "oerlikon": "Oerlikon",
        "seebach": "Seebach",
        "wipkingen": "Wipkingen",
        "altstetten": "Altstetten",
        "oerlikon zürich": "Oerlikon",
        "quartier oerlikon": "Oerlikon",
    }
    key = neigh.lower().strip().replace(" ", "-").replace("quartier-", "")
    return mapping.get(key, neigh.title())


def is_month_to_month_friendly(listing: ApartmentListing) -> bool:
    """Relaxed check for flexible/serviced listings"""
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
