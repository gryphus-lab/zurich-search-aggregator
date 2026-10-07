"""
Job backend selection.

Two interchangeable backends expose the same ``submit`` / ``get`` surface:

- ``memory`` (default): in-process :class:`~src.aggregator.jobs.JobStore`.
  Zero dependencies, no broker - great for local/dev and single instances.
- ``rq``: durable, out-of-process :class:`~src.aggregator.jobs_rq.RQJobStore`
  (Redis + RQ), a lightweight JobRunr-style queue that survives restarts and
  scales across workers. Requires the ``rq`` extra and ``JOB_BACKEND=rq``.

The API calls :func:`enqueue_search`, which adapts the search parameters to
whichever backend is active, so the route code stays backend-agnostic.
"""

from __future__ import annotations

import os
from functools import partial
from typing import Optional

import httpx

from .jobs import Job
from .logger import logger
from .service import search_apartments


def get_backend_name() -> str:
    """Return the configured backend name ('memory' or 'rq')."""
    return os.environ.get("JOB_BACKEND", "memory").strip().lower()


def build_store():
    """Instantiate the configured job store."""
    if get_backend_name() == "rq":
        from .jobs_rq import RQJobStore

        return RQJobStore()

    from .jobs import JobStore

    return JobStore()


def enqueue_search(store, params: dict, callback_url: Optional[str]) -> Job:
    """
    Enqueue a search on ``store``, adapting to its backend type.

    - RQ backend: pass ``params`` straight through (RQ serializes the work).
    - In-process backend: bind ``params`` into a zero-arg callable and provide
      a webhook ``on_complete`` hook.
    """
    # RQ store is detected structurally to avoid importing the optional module.
    if store.__class__.__name__ == "RQJobStore":
        return store.submit(params=params, callback_url=callback_url)

    work = partial(search_apartments, **params)
    on_complete = _memory_callback if callback_url else None
    return store.submit(work, callback_url=callback_url, on_complete=on_complete)


def _memory_callback(job: Job) -> None:
    """Webhook delivery for the in-process backend (best-effort)."""
    if not job.callback_url:
        return
    payload = {
        "job_id": job.id,
        "status": job.status.value,
        "count": None if job.result is None else len(job.result),
        "listings": None
        if job.result is None
        else [item.model_dump(mode="json") for item in job.result],
        "error": job.error,
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            client.post(job.callback_url, json=payload)
    except Exception as exc:  # noqa: BLE001 - best-effort webhook
        logger.error("Callback POST to %s failed: %s", job.callback_url, exc)
