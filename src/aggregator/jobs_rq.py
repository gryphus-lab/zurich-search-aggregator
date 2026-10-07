"""
RQ-backed job store (durable, out-of-process) - a lightweight, JobRunr-style
alternative to the in-process :class:`~src.aggregator.jobs.JobStore`.

Like JobRunr, jobs are persisted (here in Redis) and executed by separate
worker processes, so they survive API restarts and scale horizontally. Enabled
with ``JOB_BACKEND=rq``; otherwise the zero-dependency in-process store is used.

Requires the ``rq`` extra:  uv sync --extra rq
Run a worker:  rq worker --url "$REDIS_URL" searches
"""

from __future__ import annotations

import os
from datetime import timezone
from typing import List, Optional

import httpx

from .jobs import Job, JobStatus
from .logger import logger
from .models import ApartmentListing
from .service import search_apartments

# RQ queue name and webhook timeout.
QUEUE_NAME = "searches"
_CALLBACK_TIMEOUT_S = 15.0
# Keep finished jobs (and their results) in Redis for this long.
_RESULT_TTL_S = 24 * 60 * 60


# ---------------------------------------------------------------------------
# Worker-side functions (must be importable by the RQ worker; no closures)
# ---------------------------------------------------------------------------


def run_search_job(params: dict) -> List[dict]:
    """
    Execute a search on an RQ worker and return JSON-serializable listings.

    Returns a list of dicts (not ApartmentListing) so the result stored in
    Redis stays plain/portable.
    """
    listings = search_apartments(**params)
    return [item.model_dump(mode="json") for item in listings]


def deliver_callback(job, connection, result, *args, **kwargs) -> None:
    """RQ ``on_success`` hook: POST the finished result to the callback URL."""
    callback_url = (job.meta or {}).get("callback_url")
    if not callback_url:
        return
    payload = {
        "job_id": job.id,
        "status": JobStatus.DONE.value,
        "count": len(result or []),
        "listings": result,
    }
    _post_callback(callback_url, payload)


def deliver_callback_failure(job, connection, exc_type, exc_value, tb) -> None:
    """RQ ``on_failure`` hook: POST the failure to the callback URL."""
    callback_url = (job.meta or {}).get("callback_url")
    if not callback_url:
        return
    payload = {
        "job_id": job.id,
        "status": JobStatus.ERROR.value,
        "error": str(exc_value),
        "listings": None,
    }
    _post_callback(callback_url, payload)


def _post_callback(url: str, payload: dict) -> None:
    try:
        with httpx.Client(timeout=_CALLBACK_TIMEOUT_S) as client:
            client.post(url, json=payload)
    except Exception as exc:  # noqa: BLE001 - best-effort webhook
        logger.error("Callback POST to %s failed: %s", url, exc)


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

# RQ status string -> our JobStatus.
_STATUS_MAP = {
    "queued": JobStatus.PENDING,
    "deferred": JobStatus.PENDING,
    "scheduled": JobStatus.PENDING,
    "started": JobStatus.RUNNING,
    "finished": JobStatus.DONE,
    "failed": JobStatus.ERROR,
    "stopped": JobStatus.ERROR,
    "canceled": JobStatus.ERROR,
}


class RQJobStore:
    """
    Durable job store backed by Redis + RQ.

    Exposes the same ``submit`` / ``get`` surface as the in-process JobStore so
    the API code is backend-agnostic. The actual work runs in a separate RQ
    worker process (``rq worker searches``).
    """

    def __init__(self, redis_url: Optional[str] = None) -> None:
        # Imported lazily so the base install (without the rq extra) still works.
        from redis import Redis
        from rq import Queue

        url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        self._redis = Redis.from_url(url)
        self._queue = Queue(QUEUE_NAME, connection=self._redis)

    def submit(
        self,
        *,
        params: Optional[dict] = None,
        callback_url: Optional[str] = None,
    ) -> Job:
        """
        Enqueue a search job on the RQ queue.

        Unlike the in-process store, the work is identified by ``params`` (a
        plain dict passed to :func:`run_search_job` on the worker), because RQ
        serializes the function reference + args rather than a closure. Webhook
        delivery uses RQ's own on_success/on_failure hooks (not an on_complete
        callback), so this signature intentionally omits ``work``/``on_complete``.
        """
        from rq import Callback

        if params is None:
            raise ValueError("RQJobStore.submit requires params=<search kwargs>")

        rq_job = self._queue.enqueue(
            run_search_job,
            params,
            result_ttl=_RESULT_TTL_S,
            failure_ttl=_RESULT_TTL_S,
            on_success=Callback(deliver_callback) if callback_url else None,
            on_failure=Callback(deliver_callback_failure) if callback_url else None,
            meta={"callback_url": callback_url} if callback_url else {},
        )
        return self._to_job(rq_job)

    def get(self, job_id: str) -> Optional[Job]:
        from rq.job import Job as RQJob
        from rq.exceptions import NoSuchJobError

        try:
            rq_job = RQJob.fetch(job_id, connection=self._redis)
        except NoSuchJobError:
            return None
        return self._to_job(rq_job)

    def _to_job(self, rq_job) -> Job:
        status = _STATUS_MAP.get(rq_job.get_status(refresh=True), JobStatus.PENDING)

        result: Optional[List[ApartmentListing]] = None
        if status is JobStatus.DONE and rq_job.result is not None:
            result = [ApartmentListing(**item) for item in rq_job.result]

        error: Optional[str] = None
        if status is JobStatus.ERROR:
            error = (
                rq_job.latest_result().exc_string
                if rq_job.latest_result()
                else (rq_job.exc_info or "Job failed")
            )

        return Job(
            id=rq_job.id,
            status=status,
            created_at=_aware(rq_job.created_at),
            started_at=_aware(rq_job.started_at),
            finished_at=_aware(rq_job.ended_at),
            result=result,
            error=error,
            callback_url=(rq_job.meta or {}).get("callback_url"),
        )


def _aware(dt):
    """RQ stores naive UTC datetimes; tag them as UTC for the API views."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
