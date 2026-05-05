"""
Tests for src/aggregator/scrapers/__init__.py  (run_all_scrapers).

The Playwright-based scraper functions (scrape_flatfox, scrape_blueground,
scrape_homegate, scrape_ums) are mocked so no browser is launched.
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


@patch("src.aggregator.scrapers.scrape_ums")
@patch("src.aggregator.scrapers.scrape_homegate")
@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_combines_both_sources(
    mock_flatfox, mock_blueground, mock_homegate, mock_ums
):
    ff_listing = _make_listing("flatfox", "https://flatfox.ch/flat/1")
    bg_listing = _make_listing("blueground", "https://theblueground.com/p/1")

    mock_flatfox.return_value = [ff_listing]
    mock_blueground.return_value = [bg_listing]
    mock_homegate.return_value = []
    mock_ums.return_value = []

    result = run_all_scrapers(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert len(result) == 2
    sources = {r.source for r in result}
    assert sources == {"flatfox", "blueground"}


@patch("src.aggregator.scrapers.scrape_ums")
@patch("src.aggregator.scrapers.scrape_homegate")
@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_passes_parameters_to_flatfox(
    mock_flatfox, mock_blueground, mock_homegate, mock_ums
):
    """
    Verifies that run_all_scrapers forwards the price range, neighborhoods, move-in date, and max_pages parameters to the Flatfox scraper.

    Calls run_all_scrapers with specific filters and asserts scrape_flatfox is invoked exactly once with those same arguments.
    """
    mock_flatfox.return_value = []
    mock_blueground.return_value = []
    mock_homegate.return_value = []
    mock_ums.return_value = []

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


@patch("src.aggregator.scrapers.scrape_ums")
@patch("src.aggregator.scrapers.scrape_homegate")
@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_passes_parameters_to_blueground(
    mock_flatfox, mock_blueground, mock_homegate, mock_ums
):
    mock_flatfox.return_value = []
    mock_blueground.return_value = []
    mock_homegate.return_value = []
    mock_ums.return_value = []

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


@patch("src.aggregator.scrapers.scrape_ums")
@patch("src.aggregator.scrapers.scrape_homegate")
@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_returns_empty_list_when_both_scrapers_return_nothing(
    mock_flatfox, mock_blueground, mock_homegate, mock_ums
):
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


@patch("src.aggregator.scrapers.scrape_ums")
@patch("src.aggregator.scrapers.scrape_homegate")
@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_continues_if_flatfox_raises(
    mock_flatfox, mock_blueground, mock_homegate, mock_ums
):
    """A Flatfox failure must not prevent Blueground results from being returned."""
    mock_flatfox.side_effect = RuntimeError("Network error")
    bg_listing = _make_listing("blueground", "https://theblueground.com/p/bg-1")
    mock_blueground.return_value = [bg_listing]
    mock_homegate.return_value = []
    mock_ums.return_value = []

    result = run_all_scrapers(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert len(result) == 1
    assert result[0].source == "blueground"


@patch("src.aggregator.scrapers.scrape_ums")
@patch("src.aggregator.scrapers.scrape_homegate")
@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_continues_if_blueground_raises(
    mock_flatfox, mock_blueground, mock_homegate, mock_ums
):
    """A Blueground failure must not prevent Flatfox results from being returned."""
    ff_listing = _make_listing("flatfox", "https://flatfox.ch/flat/ff-2")
    mock_flatfox.return_value = [ff_listing]
    mock_blueground.side_effect = RuntimeError("Browser crashed")
    mock_homegate.return_value = []
    mock_ums.return_value = []

    result = run_all_scrapers(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert len(result) == 1
    assert result[0].source == "flatfox"


@patch("src.aggregator.scrapers.scrape_ums")
@patch("src.aggregator.scrapers.scrape_homegate")
@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_continues_if_both_scrapers_raise(
    mock_flatfox, mock_blueground, mock_homegate, mock_ums
):
    """All scrapers failing should yield an empty list, not an exception."""
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
def test_run_all_scrapers_preserves_listing_order(
    mock_flatfox, mock_blueground, mock_homegate, mock_ums
):
    """
    Verify that listings from Flatfox appear before those from Blueground, preserving the order within each source.
    """
    ff1 = _make_listing("flatfox", "https://flatfox.ch/flat/a", price=2100.0)
    ff2 = _make_listing("flatfox", "https://flatfox.ch/flat/b", price=2200.0)
    bg1 = _make_listing("blueground", "https://theblueground.com/p/c", price=2300.0)

    mock_flatfox.return_value = [ff1, ff2]
    mock_blueground.return_value = [bg1]
    mock_homegate.return_value = []
    mock_ums.return_value = []

    result = run_all_scrapers(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert [r.source for r in result] == ["flatfox", "flatfox", "blueground"]


# ---------------------------------------------------------------------------
# New scrapers (homegate + ums) – added in this PR
# ---------------------------------------------------------------------------


@patch("src.aggregator.scrapers.scrape_ums")
@patch("src.aggregator.scrapers.scrape_homegate")
@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_combines_all_four_sources(
    mock_flatfox, mock_blueground, mock_homegate, mock_ums
):
    """Listings from all four scrapers must appear in the result."""
    ff = _make_listing("flatfox", "https://flatfox.ch/flat/ff-1")
    bg = _make_listing("blueground", "https://theblueground.com/p/bg-1")
    hg = _make_listing("homegate", "https://homegate.ch/rent/hg-1")
    ums = _make_listing("ums", "https://ums.ch/listing/ums-1")

    mock_flatfox.return_value = [ff]
    mock_blueground.return_value = [bg]
    mock_homegate.return_value = [hg]
    mock_ums.return_value = [ums]

    result = run_all_scrapers(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert len(result) == 4
    assert {r.source for r in result} == {"flatfox", "blueground", "homegate", "ums"}


@patch("src.aggregator.scrapers.scrape_ums")
@patch("src.aggregator.scrapers.scrape_homegate")
@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_passes_parameters_to_homegate(
    mock_flatfox, mock_blueground, mock_homegate, mock_ums
):
    """run_all_scrapers must forward price range, neighborhoods, and move_in_from to scrape_homegate."""
    mock_flatfox.return_value = []
    mock_blueground.return_value = []
    mock_homegate.return_value = []
    mock_ums.return_value = []

    move_in = date(2026, 7, 1)
    run_all_scrapers(
        price_min=1900,
        price_max=2900,
        neighborhoods=["Wipkingen"],
        move_in_from=move_in,
        max_pages=2,
    )

    mock_homegate.assert_called_once_with(
        price_min=1900,
        price_max=2900,
        neighborhoods=["Wipkingen"],
        move_in_from=move_in,
    )


@patch("src.aggregator.scrapers.scrape_ums")
@patch("src.aggregator.scrapers.scrape_homegate")
@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_passes_parameters_to_ums(
    mock_flatfox, mock_blueground, mock_homegate, mock_ums
):
    """run_all_scrapers must forward price range, neighborhoods, and move_in_from to scrape_ums."""
    mock_flatfox.return_value = []
    mock_blueground.return_value = []
    mock_homegate.return_value = []
    mock_ums.return_value = []

    move_in = date(2026, 8, 1)
    run_all_scrapers(
        price_min=2000,
        price_max=3000,
        neighborhoods=["Altstetten", "Seebach"],
        move_in_from=move_in,
        max_pages=4,
    )

    mock_ums.assert_called_once_with(
        price_min=2000,
        price_max=3000,
        neighborhoods=["Altstetten", "Seebach"],
        move_in_from=move_in,
    )


@patch("src.aggregator.scrapers.scrape_ums")
@patch("src.aggregator.scrapers.scrape_homegate")
@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_continues_if_homegate_raises(
    mock_flatfox, mock_blueground, mock_homegate, mock_ums
):
    """A Homegate failure must not prevent results from other scrapers being returned."""
    ff = _make_listing("flatfox", "https://flatfox.ch/flat/x")
    mock_flatfox.return_value = [ff]
    mock_blueground.return_value = []
    mock_homegate.side_effect = RuntimeError("Homegate timeout")
    mock_ums.return_value = []

    result = run_all_scrapers(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert len(result) == 1
    assert result[0].source == "flatfox"


@patch("src.aggregator.scrapers.scrape_ums")
@patch("src.aggregator.scrapers.scrape_homegate")
@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_continues_if_ums_raises(
    mock_flatfox, mock_blueground, mock_homegate, mock_ums
):
    """A UMS failure must not prevent results from other scrapers being returned."""
    hg = _make_listing("homegate", "https://homegate.ch/rent/hg-2")
    mock_flatfox.return_value = []
    mock_blueground.return_value = []
    mock_homegate.return_value = [hg]
    mock_ums.side_effect = RuntimeError("UMS down")

    result = run_all_scrapers(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert len(result) == 1
    assert result[0].source == "homegate"


@patch("src.aggregator.scrapers.scrape_ums")
@patch("src.aggregator.scrapers.scrape_homegate")
@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_source_order_is_flatfox_blueground_homegate_ums(
    mock_flatfox, mock_blueground, mock_homegate, mock_ums
):
    """Listings are appended in the order scrapers run: flatfox → blueground → homegate → ums."""
    ff = _make_listing("flatfox", "https://flatfox.ch/flat/ord-1")
    bg = _make_listing("blueground", "https://theblueground.com/p/ord-2")
    hg = _make_listing("homegate", "https://homegate.ch/rent/ord-3")
    u = _make_listing("ums", "https://ums.ch/listing/ord-4")

    mock_flatfox.return_value = [ff]
    mock_blueground.return_value = [bg]
    mock_homegate.return_value = [hg]
    mock_ums.return_value = [u]

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
def test_run_all_scrapers_homegate_and_ums_called_once_each(
    mock_flatfox, mock_blueground, mock_homegate, mock_ums
):
    """scrape_homegate and scrape_ums must each be invoked exactly once per run_all_scrapers call."""
    mock_flatfox.return_value = []
    mock_blueground.return_value = []
    mock_homegate.return_value = []
    mock_ums.return_value = []

    run_all_scrapers(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    mock_homegate.assert_called_once()
    mock_ums.assert_called_once()


@patch("src.aggregator.scrapers.scrape_ums")
@patch("src.aggregator.scrapers.scrape_homegate")
@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_homegate_ums_results_merged_with_others(
    mock_flatfox, mock_blueground, mock_homegate, mock_ums
):
    """Total result count equals the sum across all four scrapers."""
    mock_flatfox.return_value = [
        _make_listing("flatfox", f"https://flatfox.ch/flat/{i}") for i in range(3)
    ]
    mock_blueground.return_value = [
        _make_listing("blueground", f"https://theblueground.com/p/{i}") for i in range(2)
    ]
    mock_homegate.return_value = [
        _make_listing("homegate", f"https://homegate.ch/rent/{i}") for i in range(4)
    ]
    mock_ums.return_value = [
        _make_listing("ums", f"https://ums.ch/listing/{i}") for i in range(1)
    ]

    result = run_all_scrapers(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert len(result) == 10


@patch("src.aggregator.scrapers.scrape_ums")
@patch("src.aggregator.scrapers.scrape_homegate")
@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_homegate_only_returns_results(
    mock_flatfox, mock_blueground, mock_homegate, mock_ums
):
    """When only homegate returns listings, they must appear in the result."""
    hg = _make_listing("homegate", "https://homegate.ch/rent/solo-1")
    mock_flatfox.return_value = []
    mock_blueground.return_value = []
    mock_homegate.return_value = [hg]
    mock_ums.return_value = []

    result = run_all_scrapers(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert len(result) == 1
    assert result[0].source == "homegate"


@patch("src.aggregator.scrapers.scrape_ums")
@patch("src.aggregator.scrapers.scrape_homegate")
@patch("src.aggregator.scrapers.scrape_blueground")
@patch("src.aggregator.scrapers.scrape_flatfox")
def test_run_all_scrapers_ums_only_returns_results(
    mock_flatfox, mock_blueground, mock_homegate, mock_ums
):
    """When only UMS returns listings, they must appear in the result."""
    u = _make_listing("ums", "https://ums.ch/listing/solo-2")
    mock_flatfox.return_value = []
    mock_blueground.return_value = []
    mock_homegate.return_value = []
    mock_ums.return_value = [u]

    result = run_all_scrapers(
        price_min=1700,
        price_max=3000,
        neighborhoods=["Oerlikon"],
    )

    assert len(result) == 1
    assert result[0].source == "ums"
