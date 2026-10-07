"""
Tests for src/aggregator/scrapers/flatfox.py (scrape_flatfox URL building).

sync_playwright is mocked so no browser is launched. We assert on the search
URL requested via page.goto to verify the apartment-type / furnished behaviour.
"""

from unittest.mock import MagicMock, patch

from src.aggregator.scrapers.flatfox import scrape_flatfox


def _make_playwright_mock() -> MagicMock:
    mock_page = MagicMock()
    mock_page.locator.return_value.all.return_value = []
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


def _first_url(mock_pw_cm: MagicMock) -> str:
    page = mock_pw_cm.__enter__.return_value.chromium.launch.return_value.new_context.return_value.new_page.return_value
    return page.goto.call_args.args[0]


@patch("src.aggregator.scrapers.flatfox.sync_playwright")
def test_flatfox_default_includes_all_types_not_only_furnished(mock_sync_playwright):
    mock_sync_playwright.return_value = _make_playwright_mock()

    scrape_flatfox(neighborhoods=["Thalwil"], max_pages=1)

    url = _first_url(mock_sync_playwright.return_value)
    # Default: no furnished restriction, so all apartment types are returned.
    assert "is_furnished=true" not in url
    assert "offer_type=RENT" in url
    assert "object_category=APARTMENT" in url


@patch("src.aggregator.scrapers.flatfox.sync_playwright")
def test_flatfox_furnished_only_adds_filter(mock_sync_playwright):
    mock_sync_playwright.return_value = _make_playwright_mock()

    scrape_flatfox(neighborhoods=["Thalwil"], max_pages=1, furnished_only=True)

    url = _first_url(mock_sync_playwright.return_value)
    assert "is_furnished=true" in url


@patch("src.aggregator.scrapers.flatfox.sync_playwright")
def test_flatfox_query_encodes_location(mock_sync_playwright):
    mock_sync_playwright.return_value = _make_playwright_mock()

    scrape_flatfox(neighborhoods=["Küsnacht"], max_pages=1)

    url = _first_url(mock_sync_playwright.return_value)
    # Location is URL-encoded into the query (umlaut + comma + space).
    assert "query=" in url
    assert "K%C3%BCsnacht" in url
