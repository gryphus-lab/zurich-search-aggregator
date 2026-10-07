"""
Tests for src/aggregator/service.py (shared search core).

run_all_scrapers and apply_filters are patched so no browser/network is used.
"""

from unittest.mock import patch

import pytest

from src.aggregator.models import ApartmentListing
from src.aggregator.service import resolve_neighborhoods, search_apartments


def _listing() -> ApartmentListing:
    return ApartmentListing(
        id="1",
        title="flat",
        price_chf=2000.0,
        neighborhood="Oerlikon",
        link="https://flatfox.ch/flat/1",
        source="flatfox",
    )


# ---------------------------------------------------------------------------
# resolve_neighborhoods
# ---------------------------------------------------------------------------


def test_resolve_explicit_neighborhoods_win():
    assert resolve_neighborhoods(["Thalwil"], metro=True) == ["Thalwil"]


def test_resolve_defaults_to_city_quartiers():
    assert resolve_neighborhoods(None, metro=False) == [
        "Oerlikon",
        "Seebach",
        "Wipkingen",
        "Altstetten",
    ]


def test_resolve_metro_expands_to_full_region():
    assert len(resolve_neighborhoods(None, metro=True)) == 30


# ---------------------------------------------------------------------------
# search_apartments
# ---------------------------------------------------------------------------


@patch("src.aggregator.service.apply_filters")
@patch("src.aggregator.service.run_all_scrapers")
def test_search_wires_scrape_and_filter(mock_scrape, mock_filter):
    mock_scrape.return_value = [_listing()]
    mock_filter.return_value = [_listing()]

    result = search_apartments(price_min=1700, price_max=3000, metro=True)

    assert len(result) == 1
    # Scrape ran over the metro region with validated (all) sources.
    scrape_kwargs = mock_scrape.call_args.kwargs
    assert len(scrape_kwargs["neighborhoods"]) == 30
    assert scrape_kwargs["sources"] == ["flatfox", "blueground", "homegate", "ums"]


@patch("src.aggregator.service.apply_filters")
@patch("src.aggregator.service.run_all_scrapers")
def test_search_rejects_unknown_source(mock_scrape, mock_filter):
    with pytest.raises(ValueError):
        search_apartments(sources=["zillow"])

    mock_scrape.assert_not_called()
