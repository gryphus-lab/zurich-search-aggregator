"""
Tests for src/aggregator/locations.py and its wiring into normalization.

Covers:
  - the registry resolves canonical names, aliases, and messy input
  - coordinates and city-quartier classification
  - the default search sets (city quartiers vs full metro region)
  - normalize_neighborhood resolves metro municipalities via the registry
"""

from src.aggregator import locations as L
from src.aggregator.utils import normalize_neighborhood


# ---------------------------------------------------------------------------
# Registry membership / corridors
# ---------------------------------------------------------------------------


def test_all_locations_covers_every_corridor():
    corridors = set(L.locations_by_corridor().keys())
    assert corridors == {
        "Zurich City",
        "West (Limmattal / A1)",
        "North / North-East (Glattal)",
        "North-West (Furttal)",
        "South (Sihltal / Left Bank)",
        "East (Gold Coast)",
    }


def test_full_metro_search_includes_city_and_all_corridors():
    metro = L.default_metro_search()
    # 4 city quartiers + 26 metro municipalities = 30
    assert len(metro) == 30
    for name in [
        "Oerlikon",
        "Schlieren",
        "Dietikon",
        "Wallisellen",
        "Dübendorf",
        "Opfikon",
        "Kloten",
        "Regensdorf",
        "Buchs (ZH)",
        "Adliswil",
        "Thalwil",
        "Zollikon",
        "Küsnacht",
        "Erlenbach",
    ]:
        assert name in metro


def test_default_zurich_quartiers_unchanged():
    assert L.default_zurich_quartiers() == [
        "Oerlikon",
        "Seebach",
        "Wipkingen",
        "Altstetten",
    ]


# ---------------------------------------------------------------------------
# Lookup: canonical, aliases, messy input
# ---------------------------------------------------------------------------


def test_lookup_canonical_name():
    assert L.canonical_name("Schlieren") == "Schlieren"


def test_lookup_resolves_glattbrugg_alias_to_opfikon():
    assert L.canonical_name("glattbrugg") == "Opfikon"
    assert L.canonical_name("Opfikon / Glattbrugg") == "Opfikon"


def test_lookup_resolves_bruttisellen_alias():
    assert L.canonical_name("Brüttisellen") == "Wangen-Brüttisellen"
    assert L.canonical_name("wangen bruttisellen") == "Wangen-Brüttisellen"


def test_lookup_handles_ascii_fallbacks_for_umlauts():
    assert L.canonical_name("dallikon") == "Dällikon"
    assert L.canonical_name("kusnacht") == "Küsnacht"
    assert L.canonical_name("ruschlikon") == "Rüschlikon"


def test_lookup_strips_zh_suffix():
    assert L.canonical_name("Buchs ZH") == "Buchs (ZH)"
    assert L.canonical_name("Küsnacht ZH") == "Küsnacht"


def test_lookup_unknown_returns_none():
    assert L.lookup("Atlantis") is None
    assert L.canonical_name("Atlantis") is None


# ---------------------------------------------------------------------------
# Coordinates & city classification
# ---------------------------------------------------------------------------


def test_coords_for_known_location():
    assert L.coords_for("Oerlikon") == (47.41408, 8.5445)


def test_coords_for_unknown_falls_back_to_zurich_centre():
    assert L.coords_for("Atlantis") == L.ZURICH_CENTRE


def test_is_zurich_quartier_classification():
    assert L.is_zurich_quartier("Oerlikon") is True
    assert L.is_zurich_quartier("Altstetten") is True
    assert L.is_zurich_quartier("Schlieren") is False
    assert L.is_zurich_quartier("Thalwil") is False


# ---------------------------------------------------------------------------
# normalize_neighborhood wiring (backward-compat + new metro towns)
# ---------------------------------------------------------------------------


def test_normalize_keeps_city_quartiers():
    assert normalize_neighborhood("oerlikon") == "Oerlikon"
    assert normalize_neighborhood("Altstetten") == "Altstetten"


def test_normalize_resolves_metro_municipalities():
    assert normalize_neighborhood("schlieren") == "Schlieren"
    assert normalize_neighborhood("thalwil") == "Thalwil"
    assert normalize_neighborhood("glattbrugg") == "Opfikon"


def test_normalize_unknown_still_title_cases():
    # Preserves the original fallback contract for unknown inputs.
    assert normalize_neighborhood("hard") == "Hard"
    assert normalize_neighborhood("ZURICH WEST") == "Zurich West"
