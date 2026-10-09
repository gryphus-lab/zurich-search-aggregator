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
from pathlib import Path
from typing import Optional

import httpx

from .export import write_csv
from .jobs import Job
from .logger import logger
from .service import search_apartments


def get_backend_name() -> str:
    """Return the configured backend name ('memory' or 'rq')."""
    return os.environ.get("JOB_BACKEND", "memory").strip().lower()


def results_dir() -> Path:
    """Directory where per-job result JSON files are written."""
    return Path(os.environ.get("RESULTS_DIR", "results"))


def result_filename(job_id: str) -> str:
    """
    Per-job result filename. CSV is the default output format; the fixed
    'latest.csv' name is suffixed with the job id so each run is preserved
    rather than overwriting the previous one.
    """
    return f"latest-{job_id}.csv"


def persist_result(job: Job) -> Optional[str]:
    """
    Write a finished job's listings to results/latest-<job_id>.csv.

    Returns the filename on success (so it can be recorded on the job), or None
    if there is nothing to write.
    """
    if job.result is None:
        return None
    directory = results_dir()
    directory.mkdir(parents=True, exist_ok=True)
    filename = result_filename(job.id)
    write_csv(job.result, directory / filename)
    logger.info("Job %s results saved to %s", job.id, filename)
    return filename


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
    return store.submit(
        work, callback_url=callback_url, on_complete=_on_memory_job_complete
    )


def _on_memory_job_complete(job: Job) -> None:
    """
    Completion hook for the in-process backend.

    Persists the results to a per-job file (recording the filename on the job)
    and, if a callback_url was supplied, delivers the webhook. Both steps are
    best-effort and never raise into the worker thread.
    """
    if job.status.value == "done":
        try:
            job.result_file = persist_result(job)
        except Exception as exc:  # noqa: BLE001 - best-effort persistence
            logger.error("Job %s result persistence failed: %s", job.id, exc)

    if job.callback_url:
        _deliver_callback(job)


def _deliver_callback(job: Job) -> None:
    """Webhook delivery for the in-process backend (best-effort)."""
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
