"""
Tests for src/aggregator/scrapers/__init__.py  (run_all_scrapers).

The Playwright-based scraper functions (scrape_flatfox, scrape_blueground)
are mocked so no browser is launched.
"""

from datetime import date
from unittest.mock import patch


from src.aggregator.models import ApartmentListing
from src.aggregator.scrapers import run_all_scrapers


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_listing(source: str, link: str, price: float = 2000.0) -> ApartmentListing:
    """
    Create a test ApartmentListing with the given source, link, and price.

    Parameters:
        source (str): Origin identifier for the listing (e.g., "flatfox", "blueground").
        link (str): URL or path for the listing; the listing's `id` is taken from the last path segment of this value.
        price (float): Price in CHF to set on the listing (default 2000.0).

    Returns:
        ApartmentListing: An ApartmentListing populated with the provided `source`, `link`, and `price_chf`, and with fixed `title` ("Test flat") and `neighborhood` ("Oerlikon").
    """
    return ApartmentListing(
        id=link.split("/")[-1],
        title="Test flat",
        price_chf=price,
        neighborhood="Oerlikon",
        link=link,
        source=source,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_combines_both_sources(mock_flatfox, mock_blueground):
    ff_listing = _make_listing("flatfox", "https://flatfox.ch/flat/1")
    bg_listing = _make_listing("blueground", "https://theblueground.com/p/1")

    mock_flatfox.return_value = [ff_listing]
    mock_blueground.return_value = [bg_listing]

    result = run_all_scrapers(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert len(result) == 2
    sources = {r.source for r in result}
    assert sources == {"flatfox", "blueground"}


@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_passes_parameters_to_flatfox(mock_flatfox, mock_blueground):
    """
    Verifies that run_all_scrapers forwards the price range, neighborhoods, move-in date, and max_pages parameters to the Flatfox scraper.

    Calls run_all_scrapers with specific filters and asserts scrape_flatfox is invoked exactly once with those same arguments.
    """
    mock_flatfox.return_value = []
    mock_blueground.return_value = []

    move_in = date(2026, 6, 1)
    run_all_scrapers(
        price_min=1800,
        price_max=2800,
        neighborhoods=["Seebach", "Wipkingen"],
        move_in_from=move_in,
        max_pages=3,
    )

    mock_flatfox.assert_called_once_with(
        price_min=1800,
        price_max=2800,
        neighborhoods=["Seebach", "Wipkingen"],
        move_in_from=move_in,
        max_pages=3,
    )


@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_passes_parameters_to_blueground(
    mock_flatfox, mock_blueground
):
    mock_flatfox.return_value = []
    mock_blueground.return_value = []

    move_in = date(2026, 6, 1)
    run_all_scrapers(
        price_min=1800,
        price_max=2800,
        neighborhoods=["Altstetten"],
        move_in_from=move_in,
        max_pages=2,
    )

    mock_blueground.assert_called_once_with(
        price_min=1800,
        price_max=2800,
        neighborhoods=["Altstetten"],
        move_in_from=move_in,
    )


@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_returns_empty_list_when_both_scrapers_return_nothing(
    mock_flatfox, mock_blueground
):
    mock_flatfox.return_value = []
    mock_blueground.return_value = []

    result = run_all_scrapers(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert result == []


@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_continues_if_flatfox_raises(mock_flatfox, mock_blueground):
    """A Flatfox failure must not prevent Blueground results from being returned."""
    mock_flatfox.side_effect = RuntimeError("Network error")
    bg_listing = _make_listing("blueground", "https://theblueground.com/p/bg-1")
    mock_blueground.return_value = [bg_listing]

    result = run_all_scrapers(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert len(result) == 1
    assert result[0].source == "blueground"


@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_continues_if_blueground_raises(mock_flatfox, mock_blueground):
    """A Blueground failure must not prevent Flatfox results from being returned."""
    ff_listing = _make_listing("flatfox", "https://flatfox.ch/flat/ff-2")
    mock_flatfox.return_value = [ff_listing]
    mock_blueground.side_effect = RuntimeError("Browser crashed")

    result = run_all_scrapers(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert len(result) == 1
    assert result[0].source == "flatfox"


@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_continues_if_both_scrapers_raise(
    mock_flatfox, mock_blueground
):
    """Both scrapers failing should yield an empty list, not an exception."""
    mock_flatfox.side_effect = Exception("ff down")
    mock_blueground.side_effect = Exception("bg down")

    result = run_all_scrapers(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert result == []


@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_preserves_listing_order(mock_flatfox, mock_blueground):
    """
    Verify that listings from Flatfox appear before those from Blueground, preserving the order within each source.
    """
    ff1 = _make_listing("flatfox", "https://flatfox.ch/flat/a", price=2100.0)
    ff2 = _make_listing("flatfox", "https://flatfox.ch/flat/b", price=2200.0)
    bg1 = _make_listing("blueground", "https://theblueground.com/p/c", price=2300.0)

    mock_flatfox.return_value = [ff1, ff2]
    mock_blueground.return_value = [bg1]

    result = run_all_scrapers(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert [r.source for r in result] == ["flatfox", "flatfox", "blueground"]


# ---------------------------------------------------------------------------
# Tests for run_all_scrapers with all four scrapers (homegate + ums added in PR)
# ---------------------------------------------------------------------------


@patch("src.aggregator.scrapers.scrape_ums")
@patch("src.aggregator.scrapers.scrape_homegate")
@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_combines_all_four_sources(
    mock_flatfox, mock_blueground, mock_homegate, mock_ums
):
    """All four scrapers are called and their results merged."""
    mock_flatfox.return_value = [_make_listing("flatfox", "https://flatfox.ch/flat/1")]
    mock_blueground.return_value = [
        _make_listing("blueground", "https://theblueground.com/p/2")
    ]
    mock_homegate.return_value = [
        _make_listing("homegate", "https://www.homegate.ch/listing/3")
    ]
    mock_ums.return_value = [_make_listing("ums", "https://www.ums.ch/listing/4")]

    result = run_all_scrapers(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert len(result) == 4
    sources = {r.source for r in result}
    assert sources == {"flatfox", "blueground", "homegate", "ums"}


@patch("src.aggregator.scrapers.scrape_ums")
@patch("src.aggregator.scrapers.scrape_homegate")
@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_passes_parameters_to_homegate(
    mock_flatfox, mock_blueground, mock_homegate, mock_ums
):
    """run_all_scrapers forwards price, neighborhoods and move_in_from to scrape_homegate."""
    mock_flatfox.return_value = []
    mock_blueground.return_value = []
    mock_homegate.return_value = []
    mock_ums.return_value = []

    move_in = date(2026, 7, 1)
    run_all_scrapers(
        price_min=1800,
        price_max=2800,
        neighborhoods=["Seebach"],
        move_in_from=move_in,
    )

    mock_homegate.assert_called_once_with(
        price_min=1800,
        price_max=2800,
        neighborhoods=["Seebach"],
        move_in_from=move_in,
    )


@patch("src.aggregator.scrapers.scrape_ums")
@patch("src.aggregator.scrapers.scrape_homegate")
@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_passes_parameters_to_ums(
    mock_flatfox, mock_blueground, mock_homegate, mock_ums
):
    """run_all_scrapers forwards price, neighborhoods and move_in_from to scrape_ums."""
    mock_flatfox.return_value = []
    mock_blueground.return_value = []
    mock_homegate.return_value = []
    mock_ums.return_value = []

    move_in = date(2026, 8, 1)
    run_all_scrapers(
        price_min=1900,
        price_max=2700,
        neighborhoods=["Wipkingen"],
        move_in_from=move_in,
    )

    mock_ums.assert_called_once_with(
        price_min=1900,
        price_max=2700,
        neighborhoods=["Wipkingen"],
        move_in_from=move_in,
    )


@patch("src.aggregator.scrapers.scrape_ums")
@patch("src.aggregator.scrapers.scrape_homegate")
@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_continues_if_homegate_raises(
    mock_flatfox, mock_blueground, mock_homegate, mock_ums
):
    """A Homegate failure must not prevent other scraper results from being returned."""
    mock_flatfox.return_value = [_make_listing("flatfox", "https://flatfox.ch/flat/ff")]
    mock_blueground.return_value = []
    mock_homegate.side_effect = RuntimeError("Homegate down")
    mock_ums.return_value = [_make_listing("ums", "https://www.ums.ch/listing/ums1")]

    result = run_all_scrapers(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert len(result) == 2
    sources = {r.source for r in result}
    assert "homegate" not in sources
    assert "flatfox" in sources
    assert "ums" in sources


@patch("src.aggregator.scrapers.scrape_ums")
@patch("src.aggregator.scrapers.scrape_homegate")
@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_continues_if_ums_raises(
    mock_flatfox, mock_blueground, mock_homegate, mock_ums
):
    """A UMS failure must not prevent other scraper results from being returned."""
    mock_flatfox.return_value = []
    mock_blueground.return_value = [
        _make_listing("blueground", "https://theblueground.com/p/bg1")
    ]
    mock_homegate.return_value = [
        _make_listing("homegate", "https://www.homegate.ch/listing/hg1")
    ]
    mock_ums.side_effect = RuntimeError("UMS down")

    result = run_all_scrapers(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert len(result) == 2
    sources = {r.source for r in result}
    assert "ums" not in sources
    assert "blueground" in sources
    assert "homegate" in sources


@patch("src.aggregator.scrapers.scrape_ums")
@patch("src.aggregator.scrapers.scrape_homegate")
@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_all_four_scrapers_raise_returns_empty(
    mock_flatfox, mock_blueground, mock_homegate, mock_ums
):
    """All four scrapers failing must yield an empty list, not an exception."""
    mock_flatfox.side_effect = Exception("ff down")
    mock_blueground.side_effect = Exception("bg down")
    mock_homegate.side_effect = Exception("hg down")
    mock_ums.side_effect = Exception("ums down")

    result = run_all_scrapers(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert result == []


@patch("src.aggregator.scrapers.scrape_ums")
@patch("src.aggregator.scrapers.scrape_homegate")
@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_four_source_listing_order(
    mock_flatfox, mock_blueground, mock_homegate, mock_ums
):
    """Listings are returned in scraper invocation order: flatfox → blueground → homegate → ums."""
    ff = _make_listing("flatfox", "https://flatfox.ch/flat/f1")
    bg = _make_listing("blueground", "https://theblueground.com/p/b1")
    hg = _make_listing("homegate", "https://www.homegate.ch/listing/h1")
    um = _make_listing("ums", "https://www.ums.ch/listing/u1")

    mock_flatfox.return_value = [ff]
    mock_blueground.return_value = [bg]
    mock_homegate.return_value = [hg]
    mock_ums.return_value = [um]

    result = run_all_scrapers(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert [r.source for r in result] == ["flatfox", "blueground", "homegate", "ums"]


@patch("src.aggregator.scrapers.scrape_ums")
@patch("src.aggregator.scrapers.scrape_homegate")
@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_returns_empty_when_all_scrapers_return_nothing(
    mock_flatfox, mock_blueground, mock_homegate, mock_ums
):
    """All four scrapers returning empty lists → result is an empty list."""
    mock_flatfox.return_value = []
    mock_blueground.return_value = []
    mock_homegate.return_value = []
    mock_ums.return_value = []

    result = run_all_scrapers(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert result == []
