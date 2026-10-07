# src/aggregator/locations.py
"""
Central registry of searchable locations in the Zurich metro region.

A single source of truth for every location the aggregator searches, so that
normalization, default search sets, and per-source URL building all agree.

Each :class:`Location` carries:

- ``canonical``   - the display / canonical name (e.g. ``"Opfikon"``).
- ``aliases``     - alternative spellings or lookup keys that normalize to the
                    canonical name (e.g. ``"glattbrugg"``, ``"wangen bruttisellen"``).
- ``coords``      - ``(lat, lng)`` used by map-based sources (UMS). Falls back to
                    Zurich centre when a location has none.
- ``corridor``    - the metro corridor the location belongs to (grouping only).
- ``is_zurich_quartier`` - True for districts *inside* the city of Zurich. Only
                    these are valid for Homegate's ``district-...`` path and for
                    Blueground (which operates inside the city).

Locations outside the city (independent municipalities) are searched on the
sources that support free-text / location queries (Flatfox, Homegate location
search) and are skipped on city-only sources (Blueground).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# Zurich city centre - fallback for anything without explicit coordinates.
ZURICH_CENTRE: Tuple[float, float] = (47.3769, 8.5417)


@dataclass(frozen=True)
class Location:
    canonical: str
    coords: Tuple[float, float] = ZURICH_CENTRE
    corridor: str = "Zurich City"
    is_zurich_quartier: bool = False
    aliases: Tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
# Coordinates are municipality / quartier centroids (WGS84). They only need to
# be good enough to centre a map-radius search, not pinpoint accurate.

_LOCATIONS: Tuple[Location, ...] = (
    # --- City of Zurich quartiers (original default set) ------------------
    Location("Oerlikon", (47.41408, 8.54450), "Zurich City", True),
    Location("Seebach", (47.42360, 8.53390), "Zurich City", True),
    Location("Wipkingen", (47.39040, 8.52680), "Zurich City", True),
    Location("Altstetten", (47.38820, 8.49340), "Zurich City", True),
    # --- West Corridor (Limmattal / A1) -----------------------------------
    Location("Schlieren", (47.39660, 8.44760), "West (Limmattal / A1)"),
    Location("Dietikon", (47.40150, 8.40030), "West (Limmattal / A1)"),
    Location("Urdorf", (47.38610, 8.42660), "West (Limmattal / A1)"),
    Location("Oberengstringen", (47.41000, 8.46340), "West (Limmattal / A1)"),
    Location("Unterengstringen", (47.41160, 8.44660), "West (Limmattal / A1)"),
    Location("Geroldswil", (47.42020, 8.41280), "West (Limmattal / A1)"),
    # --- North & North-East Corridor (Glattal / A1 & A51) -----------------
    Location("Wallisellen", (47.41200, 8.59570), "North / North-East (Glattal)"),
    Location(
        "Dübendorf",
        (47.39730, 8.61850),
        "North / North-East (Glattal)",
        aliases=("dubendorf", "duebendorf"),
    ),
    Location(
        "Opfikon",
        (47.42870, 8.57150),
        "North / North-East (Glattal)",
        aliases=("glattbrugg", "opfikon glattbrugg", "opfikon-glattbrugg"),
    ),
    Location("Kloten", (47.45170, 8.58520), "North / North-East (Glattal)"),
    Location(
        "Wangen-Brüttisellen",
        (47.41070, 8.63760),
        "North / North-East (Glattal)",
        aliases=(
            "wangen bruttisellen",
            "wangen-bruttisellen",
            "brüttisellen",
            "bruttisellen",
            "wangen",
        ),
    ),
    Location("Dietlikon", (47.42080, 8.61900), "North / North-East (Glattal)"),
    Location("Volketswil", (47.39000, 8.68100), "North / North-East (Glattal)"),
    # --- North-West Corridor (Furttal / A1) -------------------------------
    Location("Regensdorf", (47.43430, 8.46700), "North-West (Furttal)"),
    Location(
        "Dällikon",
        (47.43500, 8.43530),
        "North-West (Furttal)",
        aliases=("dallikon", "daellikon"),
    ),
    Location(
        "Buchs (ZH)",
        (47.43090, 8.43330),
        "North-West (Furttal)",
        aliases=("buchs zh", "buchs"),
    ),
    Location("Otelfingen", (47.44680, 8.39670), "North-West (Furttal)"),
    # --- South Corridor (Sihl Valley & Left Bank / A3) --------------------
    Location("Adliswil", (47.31000, 8.52570), "South (Sihltal / Left Bank)"),
    Location("Kilchberg", (47.32330, 8.54260), "South (Sihltal / Left Bank)"),
    Location("Thalwil", (47.29440, 8.56460), "South (Sihltal / Left Bank)"),
    Location(
        "Rüschlikon",
        (47.30560, 8.55300),
        "South (Sihltal / Left Bank)",
        aliases=("ruschlikon", "rueschlikon"),
    ),
    Location(
        "Langnau am Albis",
        (47.28700, 8.56700),
        "South (Sihltal / Left Bank)",
        aliases=("langnau", "langnau a. albis", "langnau am albis"),
    ),
    # --- East Corridor (Right Bank / Gold Coast) --------------------------
    Location("Zollikon", (47.34090, 8.57300), "East (Gold Coast)"),
    Location("Zumikon", (47.33190, 8.61560), "East (Gold Coast)"),
    Location(
        "Küsnacht",
        (47.31770, 8.58490),
        "East (Gold Coast)",
        aliases=("kusnacht", "kuesnacht", "küsnacht zh", "kusnacht zh"),
    ),
    Location(
        "Erlenbach", (47.30320, 8.59350), "East (Gold Coast)", aliases=("erlenbach zh",)
    ),
)


def _norm_key(value: str) -> str:
    """Lowercase + strip + collapse separators to a stable lookup key."""
    key = value.lower().strip()
    for sep in ("-", "_", "/", "."):
        key = key.replace(sep, " ")
    # drop administrative noise so "Küsnacht ZH" == "Küsnacht"
    key = key.replace("quartier", " ").replace("zürich", " ").replace("zurich", " ")
    return " ".join(key.split())


# canonical-key -> Location, plus every alias-key -> Location
_LOOKUP: Dict[str, Location] = {}
for _loc in _LOCATIONS:
    _LOOKUP[_norm_key(_loc.canonical)] = _loc
    for _alias in _loc.aliases:
        _LOOKUP[_norm_key(_alias)] = _loc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def all_locations() -> List[Location]:
    """Return every registered location (city quartiers + metro municipalities)."""
    return list(_LOCATIONS)


def lookup(name: str) -> Optional[Location]:
    """Resolve a raw name (canonical, alias, or messy input) to a Location, or None."""
    if not name:
        return None
    return _LOOKUP.get(_norm_key(name))


def canonical_name(name: str) -> Optional[str]:
    """Return the canonical display name for a known location, else None."""
    loc = lookup(name)
    return loc.canonical if loc else None


def coords_for(name: str) -> Tuple[float, float]:
    """Return (lat, lng) for a known location, falling back to Zurich centre."""
    loc = lookup(name)
    return loc.coords if loc else ZURICH_CENTRE


def is_zurich_quartier(name: str) -> bool:
    """True only for districts inside the city of Zurich."""
    loc = lookup(name)
    return bool(loc and loc.is_zurich_quartier)


def default_zurich_quartiers() -> List[str]:
    """The original in-city default search set (backward-compatible)."""
    return [loc.canonical for loc in _LOCATIONS if loc.is_zurich_quartier]


def default_metro_search() -> List[str]:
    """The full metro-region search set: city quartiers + all corridors."""
    return [loc.canonical for loc in _LOCATIONS]


def locations_by_corridor() -> Dict[str, List[str]]:
    """Group canonical names by their corridor (for help text / docs)."""
    grouped: Dict[str, List[str]] = {}
    for loc in _LOCATIONS:
        grouped.setdefault(loc.corridor, []).append(loc.canonical)
    return grouped
