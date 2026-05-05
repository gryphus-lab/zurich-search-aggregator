"""
Tests for src/aggregator/utils.py (new module introduced in this PR).

Covers:
- parse_available_from  (format variants, prefix stripping, edge cases)
- normalize_neighborhood (canonical mappings, quartier- prefix, unknown values)
- is_furnished_friendly  (keyword detection, case-insensitivity, edge cases)
"""

from datetime import date

from src.aggregator.utils import (
    is_furnished_friendly,
    normalize_neighborhood,
    parse_available_from,
)


# ---------------------------------------------------------------------------
# parse_available_from – falsy / empty inputs
# ---------------------------------------------------------------------------


def test_parse_available_from_none_returns_none():
    assert parse_available_from(None) is None


def test_parse_available_from_empty_string_returns_none():
    assert parse_available_from("") is None


def test_parse_available_from_whitespace_only_returns_none():
    assert parse_available_from("   ") is None


def test_parse_available_from_unrecognisable_text_returns_none():
    assert parse_available_from("sometime soon") is None


def test_parse_available_from_only_prefix_stripped_leaves_nothing():
    """'sofort' is stripped; nothing parseable remains."""
    assert parse_available_from("sofort") is None


# ---------------------------------------------------------------------------
# parse_available_from – DD.MM.YYYY format
# ---------------------------------------------------------------------------


def test_parse_available_from_ddmmyyyy_format():
    assert parse_available_from("15.05.2026") == date(2026, 5, 15)


def test_parse_available_from_ddmmyyyy_leading_zero_day():
    assert parse_available_from("01.01.2025") == date(2025, 1, 1)


def test_parse_available_from_ab_prefix_stripped_ddmmyyyy():
    assert parse_available_from("ab 01.06.2026") == date(2026, 6, 1)


def test_parse_available_from_verfuegbar_ab_prefix_stripped():
    assert parse_available_from("verfügbar ab 15.03.2026") == date(2026, 3, 15)


def test_parse_available_from_available_from_prefix_stripped():
    assert parse_available_from("available from 01.07.2026") == date(2026, 7, 1)


def test_parse_available_from_from_prefix_stripped():
    assert parse_available_from("from 12.08.2026") == date(2026, 8, 12)


# ---------------------------------------------------------------------------
# parse_available_from – DD Mon YYYY (abbreviated month)
# ---------------------------------------------------------------------------


def test_parse_available_from_dd_mon_yyyy():
    assert parse_available_from("15 May 2026") == date(2026, 5, 15)


def test_parse_available_from_dd_mon_yyyy_prefix():
    assert parse_available_from("ab 1 Jan 2025") == date(2025, 1, 1)


def test_parse_available_from_available_dd_mon_yyyy():
    assert parse_available_from("Available 1 May 2026") == date(2026, 5, 1)


# ---------------------------------------------------------------------------
# parse_available_from – DD Month YYYY (full month name)
# ---------------------------------------------------------------------------


def test_parse_available_from_dd_month_yyyy():
    assert parse_available_from("15 March 2026") == date(2026, 3, 15)


def test_parse_available_from_dd_month_yyyy_with_prefix():
    assert parse_available_from("from 12 March 2026") == date(2026, 3, 12)


# ---------------------------------------------------------------------------
# parse_available_from – Mon DD YYYY (month first, abbreviated)
# ---------------------------------------------------------------------------


def test_parse_available_from_mon_dd_yyyy():
    assert parse_available_from("May 15 2026") == date(2026, 5, 15)


def test_parse_available_from_mon_dd_yyyy_jan():
    assert parse_available_from("Jan 1 2025") == date(2025, 1, 1)


# ---------------------------------------------------------------------------
# parse_available_from – YYYY-MM-DD ISO format
# ---------------------------------------------------------------------------


def test_parse_available_from_iso_format():
    assert parse_available_from("2026-05-01") == date(2026, 5, 1)


def test_parse_available_from_iso_format_with_from_prefix():
    assert parse_available_from("from 2026-05-01") == date(2026, 5, 1)


def test_parse_available_from_iso_format_2025():
    assert parse_available_from("2025-12-31") == date(2025, 12, 31)


# ---------------------------------------------------------------------------
# parse_available_from – returns a date object (not datetime)
# ---------------------------------------------------------------------------


def test_parse_available_from_returns_date_type():
    result = parse_available_from("15.05.2026")
    assert isinstance(result, date)
    assert type(result) is date


# ---------------------------------------------------------------------------
# parse_available_from – prefix stripping is case-insensitive
# ---------------------------------------------------------------------------


def test_parse_available_from_prefix_case_insensitive_upper():
    assert parse_available_from("FROM 01.05.2026") == date(2026, 5, 1)


def test_parse_available_from_prefix_case_insensitive_mixed():
    assert parse_available_from("Available From 2026-06-01") == date(2026, 6, 1)


# ---------------------------------------------------------------------------
# parse_available_from – regression: extra trailing text causes failure
# ---------------------------------------------------------------------------


def test_parse_available_from_trailing_text_returns_none():
    """Extra text after the date makes all formats fail."""
    assert parse_available_from("15.05.2026 or later") is None


def test_parse_available_from_only_day_month_returns_none():
    """A partial date without a year cannot be parsed."""
    assert parse_available_from("15.05") is None


# ---------------------------------------------------------------------------
# normalize_neighborhood – canonical mappings
# ---------------------------------------------------------------------------


def test_normalize_neighborhood_oerlikon_lowercase():
    assert normalize_neighborhood("oerlikon") == "Oerlikon"


def test_normalize_neighborhood_seebach_lowercase():
    assert normalize_neighborhood("seebach") == "Seebach"


def test_normalize_neighborhood_wipkingen_lowercase():
    assert normalize_neighborhood("wipkingen") == "Wipkingen"


def test_normalize_neighborhood_altstetten_lowercase():
    assert normalize_neighborhood("altstetten") == "Altstetten"


def test_normalize_neighborhood_oerlikon_uppercase():
    assert normalize_neighborhood("OERLIKON") == "Oerlikon"


def test_normalize_neighborhood_seebach_mixed_case():
    assert normalize_neighborhood("Seebach") == "Seebach"


def test_normalize_neighborhood_wipkingen_uppercase():
    assert normalize_neighborhood("WIPKINGEN") == "Wipkingen"


def test_normalize_neighborhood_altstetten_uppercase():
    assert normalize_neighborhood("ALTSTETTEN") == "Altstetten"


# ---------------------------------------------------------------------------
# normalize_neighborhood – quartier- prefix stripping
# ---------------------------------------------------------------------------


def test_normalize_neighborhood_quartier_space_oerlikon():
    """'quartier oerlikon' -> replace(' ','-') -> 'quartier-oerlikon' -> strip 'quartier-' -> 'oerlikon' -> 'Oerlikon'."""
    assert normalize_neighborhood("quartier oerlikon") == "Oerlikon"


def test_normalize_neighborhood_quartier_dash_oerlikon():
    """'quartier-oerlikon' with a real dash -> strip 'quartier-' -> 'oerlikon' -> 'Oerlikon'."""
    assert normalize_neighborhood("quartier-oerlikon") == "Oerlikon"


def test_normalize_neighborhood_Quartier_mixed_case():
    """Mixed-case 'Quartier Oerlikon' must normalise through lowercasing."""
    assert normalize_neighborhood("Quartier Oerlikon") == "Oerlikon"


def test_normalize_neighborhood_quartier_seebach():
    assert normalize_neighborhood("quartier-seebach") == "Seebach"


# ---------------------------------------------------------------------------
# normalize_neighborhood – leading/trailing whitespace
# ---------------------------------------------------------------------------


def test_normalize_neighborhood_leading_trailing_spaces():
    assert normalize_neighborhood("  oerlikon  ") == "Oerlikon"


def test_normalize_neighborhood_spaces_around_seebach():
    assert normalize_neighborhood("  Seebach  ") == "Seebach"


# ---------------------------------------------------------------------------
# normalize_neighborhood – unknown values fall back to title-case
# ---------------------------------------------------------------------------


def test_normalize_neighborhood_unknown_single_word():
    assert normalize_neighborhood("hard") == "Hard"


def test_normalize_neighborhood_unknown_multi_word():
    assert normalize_neighborhood("zurich west") == "Zurich West"


def test_normalize_neighborhood_unknown_uppercase():
    assert normalize_neighborhood("ZURICH WEST") == "Zurich West"


def test_normalize_neighborhood_unknown_mixed():
    assert normalize_neighborhood("CITY CENTER") == "City Center"


# ---------------------------------------------------------------------------
# normalize_neighborhood – returns a str
# ---------------------------------------------------------------------------


def test_normalize_neighborhood_returns_str():
    assert isinstance(normalize_neighborhood("oerlikon"), str)


# ---------------------------------------------------------------------------
# normalize_neighborhood – regression: zürich suffix is NOT stripped in new impl
# ---------------------------------------------------------------------------


def test_normalize_neighborhood_oerlikon_zuerich_not_stripped():
    """
    In the new utils.py implementation the 'zürich' suffix is NOT stripped
    (unlike the old filters.py version).  'oerlikon zürich' -> key
    'oerlikon-zürich' which is not in the mapping, so it title-cases to
    'Oerlikon Zürich'.
    """
    result = normalize_neighborhood("oerlikon zürich")
    assert result == "Oerlikon Zürich"


def test_normalize_neighborhood_seebach_zuerich_not_stripped():
    """Same regression guard for 'seebach zürich'."""
    result = normalize_neighborhood("seebach zürich")
    assert result == "Seebach Zürich"


# ---------------------------------------------------------------------------
# is_furnished_friendly – keyword detection
# ---------------------------------------------------------------------------


def test_is_furnished_friendly_moebliert():
    assert is_furnished_friendly("schöne möbliert Wohnung") is True


def test_is_furnished_friendly_furnished():
    assert is_furnished_friendly("fully furnished apartment") is True


def test_is_furnished_friendly_befristet():
    assert is_furnished_friendly("befristet verfügbar") is True


def test_is_furnished_friendly_temporary():
    assert is_furnished_friendly("temporary rental") is True


def test_is_furnished_friendly_kurzfristig():
    assert is_furnished_friendly("kurzfristig zu vermieten") is True


def test_is_furnished_friendly_sublet():
    assert is_furnished_friendly("sublet available immediately") is True


def test_is_furnished_friendly_each_keyword():
    """Every keyword in the list must independently trigger True."""
    keywords = [
        "möbliert",
        "furnished",
        "befristet",
        "temporary",
        "kurzfristig",
        "sublet",
    ]
    for kw in keywords:
        assert is_furnished_friendly(kw) is True, f"keyword '{kw}' not detected"


# ---------------------------------------------------------------------------
# is_furnished_friendly – case-insensitivity
# ---------------------------------------------------------------------------


def test_is_furnished_friendly_uppercase_keyword():
    assert is_furnished_friendly("FURNISHED APARTMENT") is True


def test_is_furnished_friendly_mixed_case_keyword():
    assert is_furnished_friendly("Temporary Rental") is True


def test_is_furnished_friendly_mixed_case_german():
    assert is_furnished_friendly("Möbliert und Befristet") is True


# ---------------------------------------------------------------------------
# is_furnished_friendly – negative cases
# ---------------------------------------------------------------------------


def test_is_furnished_friendly_no_keyword_returns_false():
    assert is_furnished_friendly("long term annual contract only") is False


def test_is_furnished_friendly_empty_string_returns_false():
    assert is_furnished_friendly("") is False


def test_is_furnished_friendly_unrelated_text_returns_false():
    assert is_furnished_friendly("3 Zimmer, 85 m², CHF 2500, Oerlikon") is False


# ---------------------------------------------------------------------------
# is_furnished_friendly – returns bool
# ---------------------------------------------------------------------------


def test_is_furnished_friendly_returns_bool_true():
    assert type(is_furnished_friendly("furnished")) is bool


def test_is_furnished_friendly_returns_bool_false():
    assert type(is_furnished_friendly("annual lease")) is bool
