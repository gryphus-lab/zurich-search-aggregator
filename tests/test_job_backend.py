"""
Tests for src/aggregator/job_backend.py (backend selection + enqueue adapter).

The RQ store is exercised with a stand-in object (no Redis needed); the
in-process path is exercised for real.
"""

from unittest.mock import patch

from src.aggregator.job_backend import (
    build_store,
    enqueue_search,
    get_backend_name,
)
from src.aggregator.jobs import JobStore


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------


def test_default_backend_is_memory(monkeypatch):
    monkeypatch.delenv("JOB_BACKEND", raising=False)
    assert get_backend_name() == "memory"
    assert isinstance(build_store(), JobStore)


def test_backend_name_from_env(monkeypatch):
    monkeypatch.setenv("JOB_BACKEND", "RQ")
    assert get_backend_name() == "rq"


def test_build_store_rq_selected(monkeypatch):
    monkeypatch.setenv("JOB_BACKEND", "rq")
    # Patch RQJobStore so no real Redis connection is attempted.
    with patch("src.aggregator.jobs_rq.RQJobStore") as mock_store:
        build_store()
        mock_store.assert_called_once()


# ---------------------------------------------------------------------------
# enqueue_search adapter
# ---------------------------------------------------------------------------


def test_enqueue_memory_backend_runs_search():
    store = JobStore()
    params = {
        "price_min": 1700,
        "price_max": 3000,
        "move_in_from": None,
        "neighborhoods": ["Oerlikon"],
        "metro": False,
        "only_flexible": True,
        "max_pages": 1,
        "sources": None,
    }

    with patch("src.aggregator.job_backend.search_apartments") as mock_search:
        mock_search.return_value = []
        job = enqueue_search(store, params, callback_url=None)

    assert job.id
    # The work bound the params and will call search_apartments on the pool.
    import time

    deadline = time.time() + 5.0
    while time.time() < deadline and not mock_search.called:
        time.sleep(0.01)
    assert mock_search.called
    assert mock_search.call_args.kwargs["neighborhoods"] == ["Oerlikon"]


def test_enqueue_rq_backend_passes_params():
    class FakeRQStore:
        """Mimics RQJobStore by class name so the adapter picks the RQ path."""

        def __init__(self):
            self.submitted = None

        def submit(self, *, params, callback_url):
            self.submitted = (params, callback_url)

            class _J:
                id = "job-1"
                status = "pending"

            return _J()

    FakeRQStore.__name__ = "RQJobStore"
    store = FakeRQStore()
    params = {"price_min": 1700, "price_max": 3000}

    job = enqueue_search(store, params, callback_url="https://hook.test")

    assert job.id == "job-1"
    assert store.submitted == (params, "https://hook.test")
