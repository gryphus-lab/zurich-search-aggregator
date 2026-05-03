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
