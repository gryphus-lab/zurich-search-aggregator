from datetime import date

from src.aggregator.scrapers.blueground import (
    parse_available_from as parse_bg_available_from,
)
from src.aggregator.scrapers.blueground import parse_blueground_card
from src.aggregator.scrapers.flatfox import (
    parse_available_from as parse_flatfox_available_from,
)
from src.aggregator.scrapers.flatfox import parse_flatfox_card


def test_blueground_parse_available_from_supported_formats():
    assert parse_bg_available_from("Available 1 May 2026") == date(2026, 5, 1)
    assert parse_bg_available_from("Available May 1 2026") == date(2026, 5, 1)
    assert parse_bg_available_from("Available 1 May 2026") == date(2026, 5, 1)
    assert parse_bg_available_from("Available 01.05.2026") == date(2026, 5, 1)


def test_blueground_parse_available_from_invalid_returns_none():
    assert parse_bg_available_from("sometime soon") is None


def test_flatfox_parse_available_from_supported_formats():
    assert parse_flatfox_available_from("ab 12.03.2026") == date(2026, 3, 12)
    assert parse_flatfox_available_from("from 12 March 2026") == date(2026, 3, 12)
    assert parse_flatfox_available_from("2026-05-01") == date(2026, 5, 1)


def test_flatfox_parse_available_from_invalid_returns_none():
    assert parse_flatfox_available_from("unknown") is None


def test_parse_blueground_card_extracts_fields_and_parses_dates():
    text = (
        "Studio • #12 • Seebach\n"
        "Available 1 May 2026\n"
        "45 m² furnished flexible month to month"
    )
    link = "https://www.theblueground.com/furnished-apartments-zurich-ch/s/seebach/listing/12345"

    listing = parse_blueground_card(
        text=text,
        link=link,
        neighborhood="Seebach",
    )

    assert listing is not None
    assert listing.id == "12345"
    assert listing.price_chf == 0.0
    assert listing.neighborhood == "Seebach"
    assert listing.address == "Seebach"
    assert listing.title.startswith("Studio")
    assert listing.size_m2 == 45.0
    assert listing.available_from == date(2026, 5, 1)
    assert "Add dates to see price" in (listing.description_snippet or "")


def test_parse_blueground_card_move_in_filter_returns_none():
    text = "Studio • #12 • Oerlikon\nAvailable 1 May 2026\n45 m² furnished"
    link = "https://www.theblueground.com/.../listing/999"

    listing = parse_blueground_card(
        text=text,
        link=link,
        neighborhood="Oerlikon",
        move_in_from=date(2026, 6, 1),
    )
    assert listing is None


def test_parse_flatfox_card_extracts_fields_and_marks_flexible():
    text = "CHF 2'100\n2 rooms\nsublet temporary furnished\nfrom 12.03.2026\n55 m²"
    link = "https://flatfox.ch/flat/abc-123"

    listing = parse_flatfox_card(
        text=text,
        link=link,
        neighborhood="Oerlikon",
    )

    assert listing is not None
    assert listing.id == "abc-123"
    assert listing.price_chf == 2100.0
    assert listing.neighborhood == "Oerlikon"
    assert listing.address == "Oerlikon"
    assert "2 rooms" in listing.title
    assert listing.size_m2 == 55.0
    assert listing.available_from == date(2026, 3, 12)
    assert (listing.description_snippet or "").startswith("[FLEXIBLE]")


def test_parse_flatfox_card_move_in_filter_returns_none():
    text = "CHF 2'000\n1 room\navailable from 12.03.2026\n30 m² furnished"
    link = "https://flatfox.ch/flat/ff-1"

    listing = parse_flatfox_card(
        text=text,
        link=link,
        neighborhood="Seebach",
        move_in_from=date(2026, 4, 1),
    )
    assert listing is None


# ---------------------------------------------------------------------------
# get_checkout_one_year_later
# ---------------------------------------------------------------------------

from src.aggregator.scrapers.blueground import get_checkout_one_year_later


def test_get_checkout_one_year_later_mid_year():
    """2026-05-01 → the last day of April the following year (2027-04-30)."""
    result = get_checkout_one_year_later(date(2026, 5, 1))
    assert result == date(2027, 4, 30)


def test_get_checkout_one_year_later_january_wraps_to_december():
    """2026-01-15 → last day of December the following year (2027-12-31)."""
    result = get_checkout_one_year_later(date(2026, 1, 15))
    assert result == date(2027, 12, 31)


def test_get_checkout_one_year_later_december():
    """2026-12-01 → last day of November the following year (2027-11-30)."""
    result = get_checkout_one_year_later(date(2026, 12, 1))
    assert result == date(2027, 11, 30)


def test_get_checkout_one_year_later_march_31():
    """2026-03-31 → last day of February the following year (2027-02-28)."""
    result = get_checkout_one_year_later(date(2026, 3, 31))
    assert result == date(2027, 2, 28)


def test_get_checkout_one_year_later_result_is_date():
    result = get_checkout_one_year_later(date(2026, 6, 1))
    assert isinstance(result, date)


# ---------------------------------------------------------------------------
# blueground parse_available_from – additional edge cases
# ---------------------------------------------------------------------------


def test_blueground_parse_available_from_none_returns_none():
    assert parse_bg_available_from(None) is None


def test_blueground_parse_available_from_empty_string_returns_none():
    assert parse_bg_available_from("") is None


def test_blueground_parse_available_from_whitespace_only_returns_none():
    assert parse_bg_available_from("   ") is None


# ---------------------------------------------------------------------------
# flatfox parse_available_from – additional edge cases
# ---------------------------------------------------------------------------


def test_flatfox_parse_available_from_none_returns_none():
    assert parse_flatfox_available_from(None) is None


def test_flatfox_parse_available_from_empty_string_returns_none():
    assert parse_flatfox_available_from("") is None


def test_flatfox_parse_available_from_sofort_keyword_stripped_returns_none():
    # "sofort" is stripped, nothing parseable remains
    assert parse_flatfox_available_from("sofort") is None


def test_flatfox_parse_available_from_verfügbar_ab_prefix_stripped():
    assert parse_flatfox_available_from("verfügbar ab 01.06.2026") == date(2026, 6, 1)


# ---------------------------------------------------------------------------
# parse_blueground_card – correct tests (no `link` kwarg, CHF required)
# ---------------------------------------------------------------------------


def test_parse_blueground_card_with_price_extracts_price():
    """CHF must be on the first line for the price regex to match."""
    text = "CHF 2500\n#42 • Oerlikon\n45 m²"

    listing = parse_blueground_card(
        text=text,
        neighborhood="Oerlikon",
    )

    assert listing is not None
    assert listing.price_chf == 2500.0


def test_parse_blueground_card_link_derived_from_title():
    """The listing link is built from the apartment number in the title."""
    text = "CHF 2300\n#7 • Wipkingen\n60 m²"

    listing = parse_blueground_card(text=text, neighborhood="Wipkingen")

    assert listing is not None
    assert "zrh-7" in listing.link


def test_parse_blueground_card_address_extracted_from_text():
    text = "CHF 2100\n#55 • Seebach North\n50 m²"

    listing = parse_blueground_card(text=text, neighborhood="Seebach")

    assert listing is not None
    assert "Seebach North" in listing.address


def test_parse_blueground_card_available_from_equals_move_in_param():
    """available_from is taken directly from move_in_from, not parsed from text."""
    move_in = date(2026, 7, 1)
    text = "CHF 2200\n#9 • Altstetten\nAvailable 1 Jun 2026\n40 m²"

    listing = parse_blueground_card(
        text=text,
        neighborhood="Altstetten",
        move_in_from=move_in,
    )

    assert listing is not None
    assert listing.available_from == move_in


def test_parse_blueground_card_no_move_in_gives_none_available_from():
    text = "CHF 1950\n#3 • Oerlikon\n35 m²"

    listing = parse_blueground_card(text=text, neighborhood="Oerlikon")

    assert listing is not None
    assert listing.available_from is None


def test_parse_blueground_card_source_is_blueground():
    text = "CHF 2000\n#1 • Oerlikon\n30 m²"
    listing = parse_blueground_card(text=text, neighborhood="Oerlikon")
    assert listing is not None
    assert listing.source == "blueground"


def test_parse_blueground_card_description_snippet_contains_add_dates():
    text = "CHF 2000\n#1 • Oerlikon\n30 m²"
    listing = parse_blueground_card(text=text, neighborhood="Oerlikon")
    assert listing is not None
    assert "Add dates to see price" in listing.description_snippet


def test_parse_blueground_card_furnished_is_true():
    text = "CHF 2000\n#1 • Oerlikon\n30 m²"
    listing = parse_blueground_card(text=text, neighborhood="Oerlikon")
    assert listing is not None
    assert listing.furnished is True


def test_parse_blueground_card_no_hash_pattern_uses_default_title():
    """When no '#N •' pattern exists, title defaults to 'Blueground Apartment'."""
    text = "CHF 2000\nStudio apartment in Oerlikon\nNice view\n40 m²"

    listing = parse_blueground_card(text=text, neighborhood="Oerlikon")

    assert listing is not None
    assert "Blueground Apartment" in listing.title


# ---------------------------------------------------------------------------
# parse_flatfox_card – additional edge cases
# ---------------------------------------------------------------------------


def test_parse_flatfox_card_text_too_short_returns_none():
    listing = parse_flatfox_card(
        text="Short",
        link="https://flatfox.ch/flat/x",
        neighborhood="Oerlikon",
    )
    assert listing is None


def test_parse_flatfox_card_empty_link_returns_none():
    text = "CHF 2'000\n2 rooms\nOerlikon furnished apartment 55 m²"
    listing = parse_flatfox_card(
        text=text,
        link="",
        neighborhood="Oerlikon",
    )
    assert listing is None


def test_parse_flatfox_card_no_price_returns_none():
    text = "Two rooms available in a nice flat with garden in Oerlikon area"
    listing = parse_flatfox_card(
        text=text,
        link="https://flatfox.ch/flat/no-price",
        neighborhood="Oerlikon",
    )
    assert listing is None


def test_parse_flatfox_card_non_flexible_text_has_no_flexible_prefix():
    text = "CHF 2'200\n3 rooms\nlong term contract only\nfrom 01.07.2026\n70 m²"
    link = "https://flatfox.ch/flat/standard-99"

    listing = parse_flatfox_card(
        text=text,
        link=link,
        neighborhood="Wipkingen",
    )

    assert listing is not None
    assert not (listing.description_snippet or "").startswith("[FLEXIBLE]")


def test_parse_flatfox_card_moebliert_keyword_marks_flexible():
    text = "CHF 1'900\n1 zimmer\nmöbliert wohnung in oerlikon\n35 m²"
    link = "https://flatfox.ch/flat/moebliert-1"

    listing = parse_flatfox_card(
        text=text,
        link=link,
        neighborhood="Oerlikon",
    )

    assert listing is not None
    assert (listing.description_snippet or "").startswith("[FLEXIBLE]")


def test_parse_flatfox_card_price_with_apostrophe_separator():
    text = "CHF 2'950\n3 rooms\nlong term apartment\n80 m²"
    link = "https://flatfox.ch/flat/apos-test"

    listing = parse_flatfox_card(
        text=text,
        link=link,
        neighborhood="Oerlikon",
    )

    assert listing is not None
    assert listing.price_chf == 2950.0


def test_parse_flatfox_card_id_taken_from_last_path_segment():
    text = "CHF 2'000\n2 rooms\nfurnished temporary flat in Seebach\n50 m²"
    link = "https://flatfox.ch/flat/seebach-xyz-789"

    listing = parse_flatfox_card(
        text=text,
        link=link,
        neighborhood="Seebach",
    )

    assert listing is not None
    assert listing.id == "seebach-xyz-789"


def test_parse_flatfox_card_no_room_pattern_uses_neighborhood_title():
    text = "CHF 2'000\nfurnished flat in oerlikon sublet available\n55 m²"
    link = "https://flatfox.ch/flat/noroom-1"

    listing = parse_flatfox_card(
        text=text,
        link=link,
        neighborhood="Oerlikon",
    )

    assert listing is not None
    assert listing.title == "Apartment in Oerlikon"
