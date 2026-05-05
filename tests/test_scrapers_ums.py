"""
Tests for src/aggregator/scrapers/ums.py  (scrape_ums).

sync_playwright is mocked throughout so no browser is launched.
"""

from datetime import date
from unittest.mock import MagicMock, patch


from src.aggregator.scrapers.ums import scrape_ums


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_card(text: str, href: str) -> MagicMock:
    """Return a MagicMock mimicking a Playwright Locator card element."""
    card = MagicMock()
    card.inner_text.return_value = text

    link_elem = MagicMock()
    link_elem.get_attribute.return_value = href
    card.locator.return_value.first = link_elem
    return card


def _make_playwright_mock(cards: list) -> MagicMock:
    """Build a fully-mocked sync_playwright context manager chain."""
    mock_page = MagicMock()
    mock_page.locator.return_value.all.return_value = cards
    mock_page.goto.return_value = None
    mock_page.wait_for_timeout.return_value = None

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context

    mock_p = MagicMock()
    mock_p.chromium.launch.return_value = mock_browser

    mock_pw_cm = MagicMock()
    mock_pw_cm.__enter__ = MagicMock(return_value=mock_p)
    mock_pw_cm.__exit__ = MagicMock(return_value=False)

    return mock_pw_cm


# ---------------------------------------------------------------------------
# Basic functionality
# ---------------------------------------------------------------------------


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_no_cards_returns_empty_list(mock_sync_playwright):
    mock_sync_playwright.return_value = _make_playwright_mock(cards=[])

    result = scrape_ums(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert result == []


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_valid_card_returns_listing(mock_sync_playwright):
    """A well-formed card produces one ApartmentListing with correct fields."""
    text = "CHF 2'200\nTemporary apartment in Oerlikon\nfrom 01.07.2026 available"
    href = "/en/listing/ums-abc-123"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_ums(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert len(result) == 1
    listing = result[0]
    assert listing.price_chf == 2200.0
    assert listing.source == "ums"
    assert listing.neighborhood == "Oerlikon"
    assert listing.furnished is True
    assert listing.id == "ums-abc-123"
    assert listing.link == "https://www.ums.ch/en/listing/ums-abc-123"


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_title_is_always_temporary_apartment(mock_sync_playwright):
    """UMS listings always have 'Temporary Apartment' as title."""
    text = "CHF 2'000\nNice place in Seebach available now today"
    href = "/listing/999"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_ums(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Seebach"],
    )

    assert len(result) == 1
    assert result[0].title == "Temporary Apartment"


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_available_from_parsed(mock_sync_playwright):
    """available_from is extracted from 'from DD.MM.YYYY' in the text."""
    text = "CHF 2'100\nOerlikon apartment from 15.08.2026 available now"
    href = "/listing/date-check"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_ums(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert len(result) == 1
    assert result[0].available_from == date(2026, 8, 15)


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_available_from_none_when_no_date_in_text(mock_sync_playwright):
    text = "CHF 2'000\nOerlikon apartment no date mentioned available now"
    href = "/listing/nodate"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_ums(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert len(result) == 1
    assert result[0].available_from is None


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_relative_href_prepends_base_url(mock_sync_playwright):
    text = "CHF 2'000\nWipkingen apartment available for rent right now"
    href = "/listing/relative-789"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_ums(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Wipkingen"],
    )

    assert len(result) == 1
    assert result[0].link == "https://www.ums.ch/listing/relative-789"


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_absolute_href_not_modified(mock_sync_playwright):
    text = "CHF 2'000\nAltstetten apartment available for rent now here"
    href = "https://www.ums.ch/listing/absolute-456"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_ums(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Altstetten"],
    )

    assert len(result) == 1
    assert result[0].link == href


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_skips_text_too_short(mock_sync_playwright):
    """Text with fewer than 30 characters is discarded."""
    short_text = "CHF 2000 short"  # < 30 chars
    href = "/listing/short"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(short_text, href)]
    )

    result = scrape_ums(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert result == []


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_skips_empty_href(mock_sync_playwright):
    text = "CHF 2'000\nOerlikon apartment available for rent now right here"
    href = ""

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_ums(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert result == []


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_skips_price_below_minimum(mock_sync_playwright):
    text = "CHF 1'000\nOerlikon cheap apartment for rent available"
    href = "/listing/cheap"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_ums(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert result == []


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_skips_price_above_maximum(mock_sync_playwright):
    text = "CHF 5'000\nOerlikon luxury apartment for rent today"
    href = "/listing/expensive"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_ums(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert result == []


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_includes_price_at_exact_boundaries(mock_sync_playwright):
    """Prices at exactly price_min and price_max must be included."""
    cards = [
        _make_mock_card(
            "CHF 1'700\nOerlikon apartment at minimum price available", "/a/min"
        ),
        _make_mock_card(
            "CHF 3'000\nOerlikon apartment at maximum price available", "/a/max"
        ),
    ]
    mock_sync_playwright.return_value = _make_playwright_mock(cards=cards)

    result = scrape_ums(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert len(result) == 2
    prices = {r.price_chf for r in result}
    assert prices == {1700.0, 3000.0}


# ---------------------------------------------------------------------------
# Flexible keyword marking
# ---------------------------------------------------------------------------


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_befristet_marks_flexible(mock_sync_playwright):
    text = "CHF 2'000\nOerlikon befristet rental apartment available"
    href = "/listing/befristet"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_ums(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert len(result) == 1
    assert (result[0].description_snippet or "").startswith("[FLEXIBLE]")


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_temporary_marks_flexible(mock_sync_playwright):
    text = "CHF 2'000\nOerlikon temporary apartment available for rent"
    href = "/listing/temporary"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_ums(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert len(result) == 1
    assert (result[0].description_snippet or "").startswith("[FLEXIBLE]")


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_moebliert_marks_flexible(mock_sync_playwright):
    text = "CHF 2'000\nOerlikon möbliert wohnung available for rent"
    href = "/listing/moebliert"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_ums(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert len(result) == 1
    assert (result[0].description_snippet or "").startswith("[FLEXIBLE]")


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_non_flexible_text_no_prefix(mock_sync_playwright):
    text = "CHF 2'000\nOerlikon long-term annual contract apartment available"
    href = "/listing/standard"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_ums(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert len(result) == 1
    assert not (result[0].description_snippet or "").startswith("[FLEXIBLE]")


# ---------------------------------------------------------------------------
# Multi-neighborhood
# ---------------------------------------------------------------------------


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_multiple_neighborhoods_all_scraped(mock_sync_playwright):
    """Cards from every requested neighborhood appear in results."""
    mock_page = MagicMock()
    mock_page.goto.return_value = None
    mock_page.wait_for_timeout.return_value = None

    call_count = [0]

    def locator_side_effect(selector):
        locator_mock = MagicMock()
        if call_count[0] == 0:
            locator_mock.all.return_value = [
                _make_mock_card("CHF 2'000\nOerlikon apartment available now", "/o/1")
            ]
        else:
            locator_mock.all.return_value = [
                _make_mock_card("CHF 2'100\nSeebach apartment available now", "/s/1")
            ]
        call_count[0] += 1
        return locator_mock

    mock_page.locator.side_effect = locator_side_effect

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page
    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context
    mock_p = MagicMock()
    mock_p.chromium.launch.return_value = mock_browser
    mock_pw_cm = MagicMock()
    mock_pw_cm.__enter__ = MagicMock(return_value=mock_p)
    mock_pw_cm.__exit__ = MagicMock(return_value=False)
    mock_sync_playwright.return_value = mock_pw_cm

    result = scrape_ums(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon", "Seebach"],
    )

    assert len(result) == 2
    neighborhoods = {r.neighborhood for r in result}
    assert "Oerlikon" in neighborhoods
    assert "Seebach" in neighborhoods


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_default_neighborhoods_are_four(mock_sync_playwright):
    """When neighborhoods=None, four default neighborhoods are used."""
    mock_page = MagicMock()
    mock_page.goto.return_value = None
    mock_page.wait_for_timeout.return_value = None
    mock_page.locator.return_value.all.return_value = []

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page
    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context
    mock_p = MagicMock()
    mock_p.chromium.launch.return_value = mock_browser
    mock_pw_cm = MagicMock()
    mock_pw_cm.__enter__ = MagicMock(return_value=mock_p)
    mock_pw_cm.__exit__ = MagicMock(return_value=False)
    mock_sync_playwright.return_value = mock_pw_cm

    scrape_ums(neighborhoods=None)

    # 4 neighborhoods × 1 page each → 4 goto calls
    assert mock_page.goto.call_count == 4


# ---------------------------------------------------------------------------
# Error resilience
# ---------------------------------------------------------------------------


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_page_goto_error_returns_empty_list(mock_sync_playwright):
    """A page.goto error must be caught; function returns an empty list."""
    mock_page = MagicMock()
    mock_page.goto.side_effect = Exception("Connection refused")
    mock_page.wait_for_timeout.return_value = None

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page
    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context
    mock_p = MagicMock()
    mock_p.chromium.launch.return_value = mock_browser
    mock_pw_cm = MagicMock()
    mock_pw_cm.__enter__ = MagicMock(return_value=mock_p)
    mock_pw_cm.__exit__ = MagicMock(return_value=False)
    mock_sync_playwright.return_value = mock_pw_cm

    result = scrape_ums(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert result == []


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_card_inner_text_error_skips_that_card(mock_sync_playwright):
    """A card that raises on inner_text() is skipped; others are processed."""
    bad_card = MagicMock()
    bad_card.inner_text.side_effect = Exception("DOM error")

    good_text = "CHF 2'000\nOerlikon apartment available for rent now"
    good_href = "/listing/good"
    good_card = _make_mock_card(good_text, good_href)

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[bad_card, good_card]
    )

    result = scrape_ums(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert len(result) == 1


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_first_neighborhood_error_continues_to_next(mock_sync_playwright):
    """An exception for one neighborhood must not prevent the next from being scraped."""
    mock_page = MagicMock()
    mock_page.wait_for_timeout.return_value = None

    call_count = [0]

    def goto_side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise Exception("First neighborhood failed")

    def locator_side_effect(selector):
        locator_mock = MagicMock()
        locator_mock.all.return_value = [
            _make_mock_card("CHF 2'000\nSeebach apartment available now", "/s/1")
        ]
        return locator_mock

    mock_page.goto.side_effect = goto_side_effect
    mock_page.locator.side_effect = locator_side_effect

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page
    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context
    mock_p = MagicMock()
    mock_p.chromium.launch.return_value = mock_browser
    mock_pw_cm = MagicMock()
    mock_pw_cm.__enter__ = MagicMock(return_value=mock_p)
    mock_pw_cm.__exit__ = MagicMock(return_value=False)
    mock_sync_playwright.return_value = mock_pw_cm

    result = scrape_ums(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon", "Seebach"],
    )

    # Oerlikon failed → caught; Seebach succeeded → 1 listing
    assert len(result) == 1
    assert result[0].neighborhood == "Seebach"


# ---------------------------------------------------------------------------
# Data model correctness
# ---------------------------------------------------------------------------


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_source_is_ums(mock_sync_playwright):
    text = "CHF 2'000\nOerlikon apartment available for rent now"
    href = "/listing/source-check"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_ums(price_min=1700, price_max=3000, neighborhoods=["Oerlikon"])

    assert result[0].source == "ums"


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_address_equals_neighborhood(mock_sync_playwright):
    text = "CHF 2'000\nSeebach apartment available for rent now"
    href = "/listing/addr-check"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_ums(price_min=1700, price_max=3000, neighborhoods=["Seebach"])

    assert result[0].address == "Seebach"


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_size_m2_is_none(mock_sync_playwright):
    """UMS scraper does not extract size_m2; it must remain None."""
    text = "CHF 2'000\nOerlikon apartment 75 sqft available for rent"
    href = "/listing/nosize"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_ums(price_min=1700, price_max=3000, neighborhoods=["Oerlikon"])

    assert result[0].size_m2 is None


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_rooms_is_none(mock_sync_playwright):
    """UMS scraper does not extract rooms; it must remain None."""
    text = "CHF 2'000\nOerlikon apartment available for rent now"
    href = "/listing/norooms"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_ums(price_min=1700, price_max=3000, neighborhoods=["Oerlikon"])

    assert result[0].rooms is None


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_description_snippet_truncated_to_400_chars(mock_sync_playwright):
    long_text = "CHF 2'000\nOerlikon apartment " + "x" * 1000
    href = "/listing/trunc"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(long_text, href)]
    )

    result = scrape_ums(price_min=1700, price_max=3000, neighborhoods=["Oerlikon"])

    assert len(result) == 1
    snippet = result[0].description_snippet or ""
    base_snippet = snippet.replace("[FLEXIBLE] ", "")
    assert len(base_snippet) <= 400


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_raw_data_contains_raw_text_key(mock_sync_playwright):
    text = "CHF 2'000\nOerlikon apartment available for rent now"
    href = "/listing/raw-check"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_ums(price_min=1700, price_max=3000, neighborhoods=["Oerlikon"])

    assert "raw_text" in result[0].raw_data


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_id_from_last_href_segment(mock_sync_playwright):
    text = "CHF 2'000\nOerlikon apartment available for rent now"
    href = "/listing/ums-listing-xyz"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_ums(price_min=1700, price_max=3000, neighborhoods=["Oerlikon"])

    assert result[0].id == "ums-listing-xyz"


@patch("src.aggregator.scrapers.ums.sync_playwright")
def test_scrape_ums_price_with_apostrophe_separator(mock_sync_playwright):
    """Apostrophe-separated Swiss price format like 2'500 must parse to 2500."""
    text = "CHF 2'500\nOerlikon apartment available for rent now"
    href = "/listing/apostrophe"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_ums(price_min=1700, price_max=3000, neighborhoods=["Oerlikon"])

    assert len(result) == 1
    assert result[0].price_chf == 2500.0
