"""
Tests for src/aggregator/jobs.py (in-process async job store).
"""

import time

from src.aggregator.jobs import JobStatus, JobStore
from src.aggregator.models import ApartmentListing


def _listing() -> ApartmentListing:
    return ApartmentListing(
        id="1",
        title="flat",
        price_chf=2000.0,
        neighborhood="Oerlikon",
        link="https://flatfox.ch/flat/1",
        source="flatfox",
    )


def _wait(store: JobStore, job_id: str, timeout: float = 5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = store.get(job_id)
        if job and job.status in (JobStatus.DONE, JobStatus.ERROR):
            return job
        time.sleep(0.01)
    return store.get(job_id)


def test_submit_returns_a_job_id():
    store = JobStore()
    # The work blocks until released, so the status is observable as not-done.
    import threading

    release = threading.Event()
    job = store.submit(lambda: release.wait() or [_listing()])

    assert job.id
    assert store.get(job.id).status in (JobStatus.PENDING, JobStatus.RUNNING)
    release.set()


def test_submit_runs_work_and_stores_result():
    store = JobStore()
    job = store.submit(lambda: [_listing()])

    finished = _wait(store, job.id)
    assert finished.status == JobStatus.DONE
    assert len(finished.result) == 1
    assert finished.started_at is not None
    assert finished.finished_at is not None


def test_failure_is_recorded_as_error():
    store = JobStore()

    def boom():
        raise RuntimeError("nope")

    job = store.submit(boom)
    finished = _wait(store, job.id)

    assert finished.status == JobStatus.ERROR
    assert "nope" in finished.error
    assert finished.result is None


def test_on_complete_hook_is_called():
    store = JobStore()
    seen = {}

    def hook(job):
        seen["status"] = job.status
        seen["count"] = len(job.result or [])

    job = store.submit(lambda: [_listing(), _listing()], on_complete=hook)
    _wait(store, job.id)

    deadline = time.time() + 2.0
    while time.time() < deadline and "status" not in seen:
        time.sleep(0.01)

    assert seen["status"] == JobStatus.DONE
    assert seen["count"] == 2


def test_get_unknown_job_is_none():
    assert JobStore().get("missing") is None
