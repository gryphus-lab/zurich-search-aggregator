# src/aggregator/utils.py
import re
from datetime import date, datetime
from typing import Optional


def parse_available_from(avail_str: Optional[str]) -> Optional[date]:
    """
    Parse a raw availability or move-in string into a standardized calendar date.

    Leading availability prefixes such as "ab", "verfügbar ab", "available from", "from", and "sofort" are removed before attempting to parse common date formats (for example "15.05.2026", "15 May 2026", "May 15 2026", and "2026-05-15").

    Parameters:
        avail_str (Optional[str]): Raw availability string, possibly including leading prefixes; may be None.

    Returns:
        Optional[date]: The parsed date if a supported format is matched, or `None` if the input is falsy or no format matches.
    """
    if not avail_str:
        return None

    # Clean common prefixes including "sofort"
    clean = re.sub(
        r"(?:ab|verfügbar ab|available(?:\s+from)?|from|sofort)\s*",
        "",
        avail_str,
        flags=re.I,
    ).strip()

    # If nothing remains after stripping, return None
    if not clean:
        return None

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

    # Try parsing German month names
    parsed = _try_parse_de_month(clean)
    if parsed:
        return parsed

    return None


def _try_parse_de_month(date_str: str) -> Optional[date]:
    """
    Parse German month names from date strings like "15 Mai 2026" or "Mai 2026".

    Parameters:
        date_str (str): Date string potentially containing German month names.

    Returns:
        Optional[date]: Parsed date or None if parsing fails.
    """
    # Map German month names (short and long forms) to month numbers
    de_months = {
        "januar": 1,
        "jan": 1,
        "februar": 2,
        "feb": 2,
        "märz": 3,
        "mär": 3,
        "maerz": 3,
        "april": 4,
        "apr": 4,
        "mai": 5,
        "juni": 6,
        "jun": 6,
        "juli": 7,
        "jul": 7,
        "august": 8,
        "aug": 8,
        "september": 9,
        "sep": 9,
        "sept": 9,
        "oktober": 10,
        "okt": 10,
        "november": 11,
        "nov": 11,
        "dezember": 12,
        "dez": 12,
    }

    # Try pattern: "15 Mai 2026", "15. Mai 2026", or "Mai 2026"
    match = re.search(r"(\d{1,2})?\s*\.?\s*([a-zäöüß]+)\s+(\d{4})", date_str, re.I)
    if match:
        day_str, month_str, year_str = match.groups()
        month_name = month_str.lower()

        if month_name in de_months:
            day = int(day_str) if day_str else 1
            month = de_months[month_name]
            year = int(year_str)

            try:
                return date(year, month, day)
            except ValueError:
                pass

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
    key = (
        neigh.lower()
        .strip()
        .replace(" ", "-")
        .replace("quartier-", "")
        .replace("zürich", "")
        .rstrip("-")
    )
    return mapping.get(key, key.replace("-", " ").title())


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
