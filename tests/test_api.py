"""
Tests for src/aggregator/api.py (FastAPI REST layer).

The scrape itself (search_apartments) is patched so no browser/network is used;
these tests cover routing, request/response shapes, and error handling.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.aggregator.api import app
from src.aggregator.models import ApartmentListing

client = TestClient(app)


def _listing(source: str = "flatfox") -> ApartmentListing:
    return ApartmentListing(
        id="1",
        title="2.5 rooms",
        price_chf=2200.0,
        neighborhood="Thalwil",
        link="https://flatfox.ch/flat/1",
        source=source,
    )


# ---------------------------------------------------------------------------
# Metadata endpoints
# ---------------------------------------------------------------------------


def test_health_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_sources_lists_all_aggregators():
    resp = client.get("/sources")
    assert resp.status_code == 200
    assert resp.json()["sources"] == ["flatfox", "blueground", "homegate", "ums"]


def test_locations_grouped_by_corridor():
    resp = client.get("/locations")
    assert resp.status_code == 200
    body = resp.json()
    assert "corridors" in body
    assert "Thalwil" in body["metro"]


# ---------------------------------------------------------------------------
# Search endpoint
# ---------------------------------------------------------------------------


@patch("src.aggregator.api.search_apartments")
def test_search_returns_listings(mock_search):
    mock_search.return_value = [_listing(), _listing("homegate")]

    resp = client.post("/search", json={"price_min": 1700, "price_max": 3000})

    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    assert len(body["listings"]) == 2
    assert body["sources"] == ["flatfox", "blueground", "homegate", "ums"]


@patch("src.aggregator.api.search_apartments")
def test_search_forwards_parameters(mock_search):
    mock_search.return_value = []

    resp = client.post(
        "/search",
        json={
            "price_min": 1800,
            "price_max": 2800,
            "metro": True,
            "sources": ["flatfox", "homegate"],
            "only_flexible": False,
            "max_pages": 2,
        },
    )

    assert resp.status_code == 200
    kwargs = mock_search.call_args.kwargs
    assert kwargs["price_min"] == 1800
    assert kwargs["price_max"] == 2800
    assert kwargs["metro"] is True
    assert kwargs["sources"] == ["flatfox", "homegate"]
    assert kwargs["only_flexible"] is False
    assert kwargs["max_pages"] == 2


@patch("src.aggregator.api.search_apartments")
def test_search_unknown_source_returns_422(mock_search):
    mock_search.side_effect = ValueError("Unknown source(s): zillow.")

    resp = client.post("/search", json={"sources": ["zillow"]})

    assert resp.status_code == 422
    assert "Unknown source" in resp.json()["detail"]


def test_search_defaults_applied_when_body_empty():
    with patch("src.aggregator.api.search_apartments") as mock_search:
        mock_search.return_value = []
        resp = client.post("/search", json={})

    assert resp.status_code == 200
    kwargs = mock_search.call_args.kwargs
    # Defaults mirror the CLI.
    assert kwargs["price_min"] == 1700
    assert kwargs["price_max"] == 3000
    assert kwargs["only_flexible"] is True
    assert kwargs["metro"] is False
