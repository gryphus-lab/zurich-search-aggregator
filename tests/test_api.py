"""
Tests for src/aggregator/api.py (async FastAPI REST layer).

search_apartments is patched so no browser/network is used. Searches run on a
background thread, so tests poll GET /search/{id} until the job settles.
"""

import time
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


def _poll(job_id: str, timeout: float = 5.0) -> dict:
    """Poll a job until it is done/error (or the timeout elapses)."""
    deadline = time.time() + timeout
    body = {}
    while time.time() < deadline:
        resp = client.get(f"/search/{job_id}")
        assert resp.status_code == 200
        body = resp.json()
        if body["status"] in ("done", "error"):
            return body
        time.sleep(0.02)
    return body


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
# Async submit + poll
# ---------------------------------------------------------------------------


@patch("src.aggregator.job_backend.search_apartments")
def test_submit_returns_202_with_job_id(mock_search):
    mock_search.return_value = []

    resp = client.post("/search", json={"price_min": 1700, "price_max": 3000})

    assert resp.status_code == 202
    body = resp.json()
    assert body["job_id"]
    assert body["status_url"] == f"/search/{body['job_id']}"
    assert resp.headers["Location"] == body["status_url"]


@patch("src.aggregator.job_backend.search_apartments")
def test_poll_returns_results_when_done(mock_search):
    mock_search.return_value = [_listing(), _listing("homegate")]

    job_id = client.post("/search", json={}).json()["job_id"]
    body = _poll(job_id)

    assert body["status"] == "done"
    assert body["count"] == 2
    assert len(body["listings"]) == 2


@patch("src.aggregator.job_backend.search_apartments")
def test_job_forwards_parameters(mock_search):
    mock_search.return_value = []

    job_id = client.post(
        "/search",
        json={
            "price_min": 1800,
            "price_max": 2800,
            "metro": True,
            "sources": ["flatfox", "homegate"],
            "only_flexible": False,
            "max_pages": 2,
        },
    ).json()["job_id"]
    _poll(job_id)

    kwargs = mock_search.call_args.kwargs
    assert kwargs["price_min"] == 1800
    assert kwargs["price_max"] == 2800
    assert kwargs["metro"] is True
    assert kwargs["sources"] == ["flatfox", "homegate"]
    assert kwargs["only_flexible"] is False
    assert kwargs["max_pages"] == 2


@patch("src.aggregator.job_backend.search_apartments")
def test_job_reports_error_status(mock_search):
    mock_search.side_effect = RuntimeError("scrape blew up")

    job_id = client.post("/search", json={}).json()["job_id"]
    body = _poll(job_id)

    assert body["status"] == "error"
    assert "scrape blew up" in body["error"]
    assert body["listings"] is None


def test_unknown_source_rejected_at_submit():
    # Validated before enqueue, so the caller gets a synchronous 422.
    resp = client.post("/search", json={"sources": ["zillow"]})
    assert resp.status_code == 422
    assert "Unknown source" in resp.json()["detail"]


def test_get_unknown_job_returns_404():
    resp = client.get("/search/does-not-exist")
    assert resp.status_code == 404


def test_defaults_applied_when_body_empty():
    with patch("src.aggregator.job_backend.search_apartments") as mock_search:
        mock_search.return_value = []
        job_id = client.post("/search", json={}).json()["job_id"]
        _poll(job_id)

    kwargs = mock_search.call_args.kwargs
    assert kwargs["price_min"] == 1700
    assert kwargs["price_max"] == 3000
    assert kwargs["only_flexible"] is True
    assert kwargs["metro"] is False


# ---------------------------------------------------------------------------
# Webhook callback
# ---------------------------------------------------------------------------


@patch("src.aggregator.job_backend.httpx.Client")
@patch("src.aggregator.job_backend.search_apartments")
def test_callback_url_posts_result(mock_search, mock_httpx_client):
    mock_search.return_value = [_listing()]
    posted = mock_httpx_client.return_value.__enter__.return_value.post

    job_id = client.post(
        "/search",
        json={"callback_url": "https://example.test/hook"},
    ).json()["job_id"]
    _poll(job_id)

    # Give the on_complete hook a moment to fire on the worker thread.
    deadline = time.time() + 2.0
    while time.time() < deadline and not posted.called:
        time.sleep(0.02)

    assert posted.called
    args, kwargs = posted.call_args
    assert args[0] == "https://example.test/hook"
    assert kwargs["json"]["status"] == "done"
    assert kwargs["json"]["count"] == 1
