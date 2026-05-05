# src/aggregator/utils.py
import re
from datetime import date, datetime
from typing import Optional


def parse_available_from(avail_str: Optional[str]) -> Optional[date]:
    """
    Parse an availability/move-in date string into a datetime.date.
    
    Attempts to parse common Swiss/German/English availability expressions (e.g., "ab 15.05.2026", "available from May 15 2026", "2026-05-15"). Returns None when the input is falsy or no supported format matches.
    
    Parameters:
        avail_str (Optional[str]): The raw availability string to parse.
    
    Returns:
        Optional[date]: A date representing the parsed availability, or `None` if parsing fails or input is empty.
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
    """
    Normalize a neighborhood name to a canonical, title-cased form for known Swiss neighborhoods.
    
    Parameters:
        neigh (str): Input neighborhood name; may include leading "quartier-" prefix, spaces, or mixed case.
    
    Returns:
        str: Canonical neighborhood name when recognized (e.g., "Oerlikon"); otherwise the input converted to title case.
    """
    mapping = {
        "oerlikon": "Oerlikon",
        "seebach": "Seebach",
        "wipkingen": "Wipkingen",
        "altstetten": "Altstetten",
    }
    key = neigh.lower().strip().replace(" ", "-").replace("quartier-", "")
    return mapping.get(key, neigh.title())


def is_furnished_friendly(text: str) -> bool:
    """
    Detects whether text suggests furnished, temporary, or short-term accommodation.
    
    Parameters:
        text (str): Text to analyze for keywords that indicate furnished, temporary, or short-term rental.
    
    Returns:
        bool: `True` if any furnishing/temporary-related keyword is present in `text`, `False` otherwise.
    """
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
