"""
Tests for src/aggregator/jobs_rq.py (RQ-backed store).

No real Redis/RQ is used: the Redis connection and RQ Queue/Job are mocked, so
these tests cover the mapping logic (RQ status -> JobStatus, result decoding,
webhook payloads) rather than live queueing.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

# The RQ backend is optional (install with `uv sync --extra rq`). Skip these
# tests cleanly when redis/rq are not installed so the base suite still passes.
pytest.importorskip("redis")
pytest.importorskip("rq")

from src.aggregator.jobs import JobStatus  # noqa: E402
from src.aggregator.models import ApartmentListing  # noqa: E402


def _rq_job(status="finished", result=None):
    job = MagicMock()
    job.id = "abc123"
    job.get_status.return_value = status
    job.result = result
    job.created_at = datetime(2026, 10, 7, 12, 0, 0)  # naive UTC, as RQ stores
    job.started_at = None
    job.ended_at = None
    job.meta = {}
    job.exc_info = None
    job.latest_result.return_value = None
    return job


def _make_store():
    with patch("redis.Redis"), patch("rq.Queue"):
        from src.aggregator.jobs_rq import RQJobStore

        return RQJobStore(redis_url="redis://localhost:6379/0")


def test_run_search_job_returns_serializable_dicts():
    from src.aggregator.jobs_rq import run_search_job

    listing = ApartmentListing(
        id="1",
        title="flat",
        price_chf=2000.0,
        neighborhood="Oerlikon",
        link="https://flatfox.ch/flat/1",
        source="flatfox",
    )
    with patch("src.aggregator.jobs_rq.search_apartments", return_value=[listing]):
        out = run_search_job({"price_min": 1700})

    assert isinstance(out, list)
    assert out[0]["neighborhood"] == "Oerlikon"


def test_to_job_maps_finished_status_and_decodes_result():
    store = _make_store()
    rq_job = _rq_job(
        status="finished",
        result=[
            {
                "id": "1",
                "title": "flat",
                "price_chf": 2000.0,
                "neighborhood": "Oerlikon",
                "link": "https://flatfox.ch/flat/1",
                "source": "flatfox",
            }
        ],
    )
    job = store._to_job(rq_job)

    assert job.status is JobStatus.DONE
    assert job.result is not None
    assert len(job.result) == 1
    assert job.result[0].neighborhood == "Oerlikon"
    # Naive RQ timestamp is tagged UTC.
    assert job.created_at.tzinfo == timezone.utc


def test_to_job_maps_started_to_running():
    store = _make_store()
    assert store._to_job(_rq_job(status="started")).status is JobStatus.RUNNING


def test_to_job_maps_failed_to_error():
    store = _make_store()
    job = store._to_job(_rq_job(status="failed"))
    assert job.status is JobStatus.ERROR


def test_deliver_callback_posts_done_payload():
    from src.aggregator.jobs_rq import deliver_callback

    job = MagicMock()
    job.id = "abc123"
    job.meta = {"callback_url": "https://hook.test"}

    with patch("src.aggregator.jobs_rq.httpx.Client") as mock_client:
        posted = mock_client.return_value.__enter__.return_value.post
        deliver_callback(job, connection=None, result=[{"x": 1}])

    assert posted.called
    assert posted.call_args.args[0] == "https://hook.test"
    assert posted.call_args.kwargs["json"]["status"] == "done"
    assert posted.call_args.kwargs["json"]["count"] == 1


def test_deliver_callback_noop_without_url():
    from src.aggregator.jobs_rq import deliver_callback

    job = MagicMock()
    job.meta = {}
    with patch("src.aggregator.jobs_rq.httpx.Client") as mock_client:
        deliver_callback(job, connection=None, result=[])
    mock_client.assert_not_called()
