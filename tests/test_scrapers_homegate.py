"""
Tests for src/aggregator/scrapers/homegate.py  (scrape_homegate).

sync_playwright is mocked throughout so no browser is launched.
"""

from datetime import date
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse


from src.aggregator.scrapers.homegate import scrape_homegate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_card(text: str, href: str) -> MagicMock:
    """Return a MagicMock that mimics a Playwright Locator card element."""
    card = MagicMock()
    card.inner_text.return_value = text

    link_elem = MagicMock()
    link_elem.get_attribute.return_value = href
    # card.locator("a").first
    card.locator.return_value.first = link_elem
    return card


def _make_playwright_mock(cards: list) -> MagicMock:
    """
    Build a fully-mocked sync_playwright context manager chain.

    Returns the top-level mock to be used with patch().
    """
    mock_page = MagicMock()
    mock_page.locator.return_value.all.return_value = cards
    mock_page.goto.return_value = None
    mock_page.wait_for_timeout.return_value = None
    mock_page.evaluate.return_value = None

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


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_no_cards_returns_empty_list(mock_sync_playwright):
    mock_sync_playwright.return_value = _make_playwright_mock(cards=[])

    result = scrape_homegate(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
        max_pages=1,
    )

    assert result == []


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_valid_card_returns_listing(mock_sync_playwright):
    """A well-formed card produces one ApartmentListing with the correct fields."""
    text = "CHF 2'500\n3 Zimmer\n75 m²\nOerlikon\nab 01.06.2026\nLong description here"
    href = "/en/rent/apartment/123456"

    cards = [_make_mock_card(text, href)]
    mock_sync_playwright.return_value = _make_playwright_mock(cards=cards)

    result = scrape_homegate(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
        max_pages=1,
    )

    assert len(result) == 1
    listing = result[0]
    assert listing.price_chf == 2500.0
    assert listing.source == "homegate"
    assert listing.neighborhood == "Oerlikon"
    assert listing.furnished is True
    assert listing.id == "123456"
    assert listing.link == "https://www.homegate.ch/en/rent/apartment/123456"


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_title_extracted_from_zimmer_pattern(mock_sync_playwright):
    text = "CHF 2'000\n2 Zimmer\n50 m²\nSeebach area listing here"
    href = "/en/rent/apartment/999"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_homegate(
        price_min=1700, price_max=3000, neighborhoods=["Seebach"], max_pages=1
    )

    assert len(result) == 1
    assert "Zimmer" in result[0].title


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_title_defaults_to_apartment_when_no_zimmer(
    mock_sync_playwright,
):
    text = "CHF 2'000\nNice flat in Oerlikon near the park area only here"
    href = "/en/rent/apartment/777"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_homegate(
        price_min=1700, price_max=3000, neighborhoods=["Oerlikon"], max_pages=1
    )

    assert len(result) == 1
    assert result[0].title == "Apartment"


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_size_extracted(mock_sync_playwright):
    text = "CHF 2'200\n2 Zimmer\n65 m²\nOerlikon nice apartment"
    href = "/en/rent/apartment/555"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_homegate(
        price_min=1700, price_max=3000, neighborhoods=["Oerlikon"], max_pages=1
    )

    assert len(result) == 1
    assert result[0].size_m2 == 65.0


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_available_from_parsed(mock_sync_playwright):
    text = "CHF 2'100\n2 Zimmer\n55 m²\nOerlikon\nab 15.07.2026"
    href = "/en/rent/apartment/101"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_homegate(
        price_min=1700, price_max=3000, neighborhoods=["Oerlikon"], max_pages=1
    )

    assert len(result) == 1
    assert result[0].available_from == date(2026, 7, 15)


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_href_prepends_base_url_for_relative_paths(
    mock_sync_playwright,
):
    text = "CHF 2'000\n2 Zimmer\n50 m²\nWipkingen apartment for rent now"
    href = "/en/rent/apartment/rel-123"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_homegate(
        price_min=1700, price_max=3000, neighborhoods=["Wipkingen"], max_pages=1
    )

    assert len(result) == 1
    parsed = urlparse(result[0].link)
    assert parsed.scheme == "https"
    assert parsed.hostname == "www.homegate.ch"


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_absolute_href_not_modified(mock_sync_playwright):
    text = "CHF 2'000\n2 Zimmer\n50 m²\nAltstetten apartment for rent today here"
    href = "https://www.homegate.ch/en/rent/apartment/abs-456"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_homegate(
        price_min=1700, price_max=3000, neighborhoods=["Altstetten"], max_pages=1
    )

    assert len(result) == 1
    assert result[0].link == href


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_skips_card_with_text_too_short(mock_sync_playwright):
    short_text = "CHF 2000 flat"  # < 40 chars
    href = "/en/rent/apartment/short"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(short_text, href)]
    )

    result = scrape_homegate(
        price_min=1700, price_max=3000, neighborhoods=["Oerlikon"], max_pages=1
    )

    assert result == []


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_skips_card_with_empty_href(mock_sync_playwright):
    text = "CHF 2'000\n2 Zimmer\n50 m²\nOerlikon apartment available for rent"
    href = ""

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_homegate(
        price_min=1700, price_max=3000, neighborhoods=["Oerlikon"], max_pages=1
    )

    assert result == []


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_skips_price_below_minimum(mock_sync_playwright):
    text = "CHF 1'500\n2 Zimmer\n50 m²\nOerlikon apartment available for rent"
    href = "/en/rent/apartment/cheap"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_homegate(
        price_min=1700, price_max=3000, neighborhoods=["Oerlikon"], max_pages=1
    )

    assert result == []


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_skips_price_above_maximum(mock_sync_playwright):
    text = "CHF 5'000\n2 Zimmer\n50 m²\nOerlikon luxury apartment for rent here"
    href = "/en/rent/apartment/expensive"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_homegate(
        price_min=1700, price_max=3000, neighborhoods=["Oerlikon"], max_pages=1
    )

    assert result == []


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_includes_price_at_exact_boundaries(mock_sync_playwright):
    texts_and_hrefs = [
        ("CHF 1'700\n2 Zimmer\n50 m²\nOerlikon apartment at price minimum", "/a/min"),
        ("CHF 3'000\n3 Zimmer\n70 m²\nOerlikon apartment at price maximum", "/a/max"),
    ]
    cards = [_make_mock_card(t, h) for t, h in texts_and_hrefs]
    mock_sync_playwright.return_value = _make_playwright_mock(cards=cards)

    result = scrape_homegate(
        price_min=1700, price_max=3000, neighborhoods=["Oerlikon"], max_pages=1
    )

    assert len(result) == 2
    prices = {r.price_chf for r in result}
    assert prices == {1700.0, 3000.0}


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_move_in_filter_excludes_earlier_date(mock_sync_playwright):
    """A card whose available_from < move_in_from must be skipped."""
    text = "CHF 2'000\n2 Zimmer\n50 m²\nOerlikon\nab 01.03.2026"
    href = "/en/rent/apartment/early"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_homegate(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
        move_in_from=date(2026, 6, 1),
        max_pages=1,
    )

    assert result == []


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_move_in_filter_keeps_equal_date(mock_sync_playwright):
    """available_from == move_in_from must NOT be excluded (strict less-than)."""
    text = "CHF 2'000\n2 Zimmer\n50 m²\nOerlikon\nab 01.06.2026"
    href = "/en/rent/apartment/exact"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_homegate(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
        move_in_from=date(2026, 6, 1),
        max_pages=1,
    )

    assert len(result) == 1


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_move_in_filter_keeps_card_without_date(mock_sync_playwright):
    """A card with no parseable available_from must not be excluded."""
    text = "CHF 2'000\n2 Zimmer\n50 m²\nOerlikon apartment no date available here"
    href = "/en/rent/apartment/nodate"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_homegate(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
        move_in_from=date(2026, 6, 1),
        max_pages=1,
    )

    assert len(result) == 1


# ---------------------------------------------------------------------------
# Flexible keyword marking
# ---------------------------------------------------------------------------


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_befristet_marks_flexible(mock_sync_playwright):
    text = "CHF 2'000\n2 Zimmer\n50 m²\nOerlikon befristet apartment available"
    href = "/en/rent/apartment/befristet"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_homegate(
        price_min=1700, price_max=3000, neighborhoods=["Oerlikon"], max_pages=1
    )

    assert len(result) == 1
    assert (result[0].description_snippet or "").startswith("[FLEXIBLE]")


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_temporary_marks_flexible(mock_sync_playwright):
    text = "CHF 2'000\n2 Zimmer\n50 m²\nOerlikon temporary rental apartment"
    href = "/en/rent/apartment/temp"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_homegate(
        price_min=1700, price_max=3000, neighborhoods=["Oerlikon"], max_pages=1
    )

    assert len(result) == 1
    assert (result[0].description_snippet or "").startswith("[FLEXIBLE]")


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_kurzfristig_marks_flexible(mock_sync_playwright):
    text = "CHF 2'000\n2 Zimmer\n50 m²\nOerlikon kurzfristig zu vermieten"
    href = "/en/rent/apartment/kurz"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_homegate(
        price_min=1700, price_max=3000, neighborhoods=["Oerlikon"], max_pages=1
    )

    assert len(result) == 1
    assert (result[0].description_snippet or "").startswith("[FLEXIBLE]")


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_moebliert_marks_flexible(mock_sync_playwright):
    text = "CHF 2'000\n2 Zimmer\n50 m²\nOerlikon möbliert wohnung available"
    href = "/en/rent/apartment/moebl"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_homegate(
        price_min=1700, price_max=3000, neighborhoods=["Oerlikon"], max_pages=1
    )

    assert len(result) == 1
    assert (result[0].description_snippet or "").startswith("[FLEXIBLE]")


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_standard_listing_no_flexible_prefix(mock_sync_playwright):
    text = "CHF 2'000\n2 Zimmer\n50 m²\nOerlikon long-term annual contract apartment"
    href = "/en/rent/apartment/standard"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_homegate(
        price_min=1700, price_max=3000, neighborhoods=["Oerlikon"], max_pages=1
    )

    assert len(result) == 1
    assert not (result[0].description_snippet or "").startswith("[FLEXIBLE]")


# ---------------------------------------------------------------------------
# Multi-neighborhood and multi-page
# ---------------------------------------------------------------------------


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_multiple_neighborhoods_all_scraped(mock_sync_playwright):
    """Listings from every requested neighborhood should appear in results."""
    text_oerlikon = "CHF 2'000\n2 Zimmer\n50 m²\nOerlikon central apartment"
    text_seebach = "CHF 2'100\n3 Zimmer\n60 m²\nSeebach nice apartment"

    mock_page = MagicMock()
    mock_page.goto.return_value = None
    mock_page.wait_for_timeout.return_value = None
    mock_page.evaluate.return_value = None

    call_count = [0]

    def locator_side_effect(selector):
        locator_mock = MagicMock()
        if call_count[0] == 0:
            # First neighborhood: Oerlikon
            locator_mock.all.return_value = [
                _make_mock_card(text_oerlikon, "/a/oerlikon")
            ]
        else:
            # Second neighborhood: Seebach
            locator_mock.all.return_value = [
                _make_mock_card(text_seebach, "/a/seebach")
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

    result = scrape_homegate(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon", "Seebach"],
        max_pages=1,
    )

    assert len(result) == 2
    neighborhoods = {r.neighborhood for r in result}
    assert "Oerlikon" in neighborhoods
    assert "Seebach" in neighborhoods


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_default_neighborhoods_are_four(mock_sync_playwright):
    """When neighborhoods=None, four default neighborhoods are used."""
    mock_page = MagicMock()
    mock_page.goto.return_value = None
    mock_page.wait_for_timeout.return_value = None
    mock_page.evaluate.return_value = None
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

    scrape_homegate(neighborhoods=None, max_pages=1)

    # 4 neighborhoods × 1 page each → 4 goto calls
    assert mock_page.goto.call_count == 4


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_max_pages_respected(mock_sync_playwright):
    """page.goto must be called max_pages times per neighborhood."""
    mock_page = MagicMock()
    mock_page.goto.return_value = None
    mock_page.wait_for_timeout.return_value = None
    mock_page.evaluate.return_value = None
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

    scrape_homegate(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
        max_pages=3,
    )

    # 1 neighborhood × 3 pages = 3 goto calls
    assert mock_page.goto.call_count == 3


# ---------------------------------------------------------------------------
# Error resilience
# ---------------------------------------------------------------------------


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_page_goto_error_does_not_raise(mock_sync_playwright):
    """A page.goto error for one neighborhood/page must be caught; function returns."""
    mock_page = MagicMock()
    mock_page.goto.side_effect = Exception("Network error")
    mock_page.wait_for_timeout.return_value = None
    mock_page.evaluate.return_value = None

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

    result = scrape_homegate(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
        max_pages=1,
    )

    assert result == []


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_card_inner_text_error_skips_card(mock_sync_playwright):
    """If inner_text() raises for a card, that card is skipped silently."""
    bad_card = MagicMock()
    bad_card.inner_text.side_effect = Exception("DOM error")

    good_card_text = "CHF 2'000\n2 Zimmer\n50 m²\nOerlikon apartment available now"
    good_card_href = "/en/rent/apartment/good"
    good_card = _make_mock_card(good_card_text, good_card_href)

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[bad_card, good_card]
    )

    result = scrape_homegate(
        price_min=1700, price_max=3000, neighborhoods=["Oerlikon"], max_pages=1
    )

    assert len(result) == 1


# ---------------------------------------------------------------------------
# Data model correctness
# ---------------------------------------------------------------------------


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_listing_source_is_homegate(mock_sync_playwright):
    text = "CHF 2'000\n2 Zimmer\n50 m²\nOerlikon apartment available for rent"
    href = "/en/rent/apartment/src-check"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_homegate(
        price_min=1700, price_max=3000, neighborhoods=["Oerlikon"], max_pages=1
    )

    assert result[0].source == "homegate"


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_listing_furnished_is_true(mock_sync_playwright):
    text = "CHF 2'000\n2 Zimmer\n50 m²\nOerlikon apartment available for rent"
    href = "/en/rent/apartment/furn-check"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_homegate(
        price_min=1700, price_max=3000, neighborhoods=["Oerlikon"], max_pages=1
    )

    assert result[0].furnished is True


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_listing_address_equals_neighborhood(mock_sync_playwright):
    text = "CHF 2'000\n2 Zimmer\n50 m²\nOerlikon apartment available for rent"
    href = "/en/rent/apartment/addr-check"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_homegate(
        price_min=1700, price_max=3000, neighborhoods=["Wipkingen"], max_pages=1
    )

    assert result[0].address == "Wipkingen"


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_description_snippet_truncated_to_450_chars(
    mock_sync_playwright,
):
    long_text = "CHF 2'000\n2 Zimmer\n50 m²\nOerlikon " + "x" * 1000
    href = "/en/rent/apartment/trunc"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(long_text, href)]
    )

    result = scrape_homegate(
        price_min=1700, price_max=3000, neighborhoods=["Oerlikon"], max_pages=1
    )

    assert len(result) == 1
    snippet = result[0].description_snippet or ""
    # Strip possible "[FLEXIBLE] " prefix before measuring base snippet length
    base_snippet = snippet.replace("[FLEXIBLE] ", "")
    assert len(base_snippet) <= 450


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_raw_data_contains_raw_text(mock_sync_playwright):
    text = "CHF 2'000\n2 Zimmer\n50 m²\nOerlikon apartment available for rent"
    href = "/en/rent/apartment/raw"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_homegate(
        price_min=1700, price_max=3000, neighborhoods=["Oerlikon"], max_pages=1
    )

    assert "raw_text" in result[0].raw_data


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_id_from_href_last_segment(mock_sync_playwright):
    text = "CHF 2'000\n2 Zimmer\n50 m²\nOerlikon apartment available for rent"
    href = "/en/rent/apartment/listing-abc-789"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_homegate(
        price_min=1700, price_max=3000, neighborhoods=["Oerlikon"], max_pages=1
    )

    assert result[0].id == "listing-abc-789"


@patch("src.aggregator.scrapers.homegate.sync_playwright")
def test_scrape_homegate_price_with_apostrophe_separator(mock_sync_playwright):
    """Apostrophe-separated price like 2'500 must be parsed as 2500."""
    text = "CHF 2'500\n3 Zimmer\n70 m²\nOerlikon luxury apartment available"
    href = "/en/rent/apartment/apos"

    mock_sync_playwright.return_value = _make_playwright_mock(
        cards=[_make_mock_card(text, href)]
    )

    result = scrape_homegate(
        price_min=1700, price_max=3000, neighborhoods=["Oerlikon"], max_pages=1
    )

    assert len(result) == 1
    assert result[0].price_chf == 2500.0
