# src/aggregator/utils.py
import re
from datetime import date, datetime
from typing import Optional


def parse_available_from(avail_str: Optional[str]) -> Optional[date]:
    """
    Robust parser for Swiss/German/English availability dates.
    Handles formats commonly seen on Homegate, Flatfox, Blueground, UMS, etc.
    """
    if not avail_str:
        return None

    # Clean common prefixes
    clean = re.sub(
        r"(?:ab|verfügbar ab|available from?|from|sofort)\s*", "", avail_str, flags=re.I
    ).strip()

    formats = [
        "%d.%m.%Y",  # 15.05.2026
        "%d %b %Y",  # 15 May 2026
        "%d %B %Y",  # 15 Mai 2026
        "%b %d %Y",  # May 15 2026
        "%Y-%m-%d",  # 2026-05-15
    ]

    for fmt in formats:
        try:
            return (
                date.fromisoformat(clean)
                if fmt == "%Y-%m-%d"
                else datetime.strptime(clean, fmt).date()
            )
        except ValueError:
            continue

    return None


def normalize_neighborhood(neigh: str) -> str:
    """Shared neighborhood normalizer"""
    mapping = {
        "oerlikon": "Oerlikon",
        "seebach": "Seebach",
        "wipkingen": "Wipkingen",
        "altstetten": "Altstetten",
    }
    key = neigh.lower().strip().replace(" ", "-").replace("quartier-", "")
    return mapping.get(key, neigh.title())


def is_furnished_friendly(text: str) -> bool:
    """Shared heuristic for furnished/temporary"""
    text_lower = text.lower()
    keywords = [
        "möbliert",
        "furnished",
        "befristet",
        "temporary",
        "kurzfristig",
        "sublet",
    ]
    return any(kw in text_lower for kw in keywords)
