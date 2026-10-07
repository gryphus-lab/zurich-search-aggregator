"""
REST API for the Zurich Search Aggregator.

A metro-wide scrape can take minutes, so searches are dispatched as async jobs
rather than held on the HTTP request:

    POST /search          -> 202 Accepted, returns a job id (and status URL)
    GET  /search/{job_id} -> poll status; includes results when done

Optionally pass ``callback_url`` in the body and the service will POST the
finished job (status + results) to that URL when it completes (webhook).

The blocking, Playwright-backed scrape runs on a background thread pool.

Run with:  uvicorn src.aggregator.api:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field, HttpUrl

from .job_backend import build_store, enqueue_search, get_backend_name
from .jobs import Job, JobStatus
from .locations import default_metro_search, locations_by_corridor
from .models import ApartmentListing
from .scrapers import AVAILABLE_SOURCES, normalize_sources

app = FastAPI(
    title="Zurich Search Aggregator",
    description=(
        "Search apartments across the Zurich metro region from multiple "
        "aggregators (Flatfox, Blueground, Homegate, UMS). Searches run as "
        "async jobs: submit via POST /search, then poll GET /search/{job_id} "
        "or receive a webhook at an optional callback_url."
    ),
    version="0.2.0",
)

# Job store, selected by JOB_BACKEND (memory | rq). The in-process default
# needs no broker; set JOB_BACKEND=rq for the durable Redis-backed queue.
_store = build_store()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SearchRequest(BaseModel):
    """Search parameters - mirrors the CLI options."""

    price_min: int = Field(1700, ge=0, description="Minimum monthly rent (CHF).")
    price_max: int = Field(3000, ge=0, description="Maximum monthly rent (CHF).")
    move_in_from: Optional[date] = Field(
        None, description="Earliest move-in date (YYYY-MM-DD)."
    )
    neighborhoods: Optional[List[str]] = Field(
        None,
        description=(
            "Locations to search. Overrides `metro`. When omitted, defaults to "
            "the city quartiers, or the whole metro region when `metro` is true."
        ),
    )
    metro: bool = Field(
        False,
        description="Search the whole metro region when no neighborhoods are given.",
    )
    only_flexible: bool = Field(
        True, description="Only month-to-month friendly listings."
    )
    max_pages: int = Field(5, ge=1, le=20, description="Max result pages per location.")
    sources: Optional[List[str]] = Field(
        None,
        description=(
            f"Aggregators to query (any of {', '.join(AVAILABLE_SOURCES)}). "
            "When omitted, all run."
        ),
    )
    callback_url: Optional[HttpUrl] = Field(
        None,
        description=(
            "Optional webhook. When set, the finished job (status + results) "
            "is POSTed to this URL once the search completes."
        ),
    )


class JobAccepted(BaseModel):
    """Returned by POST /search when a job is enqueued."""

    job_id: str
    status: JobStatus
    status_url: str = Field(description="Poll this URL for the result.")


class JobView(BaseModel):
    """Full job state returned by GET /search/{job_id} and sent to webhooks."""

    job_id: str
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
    count: Optional[int] = None
    listings: Optional[List[ApartmentListing]] = None


def _to_view(job: Job) -> JobView:
    return JobView(
        job_id=job.id,
        status=job.status,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error=job.error,
        count=None if job.result is None else len(job.result),
        listings=job.result,
    )


# ---------------------------------------------------------------------------
# Metadata endpoints
# ---------------------------------------------------------------------------


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/sources", tags=["meta"])
def sources() -> dict:
    """List the available aggregators."""
    return {"sources": AVAILABLE_SOURCES}


@app.get("/locations", tags=["meta"])
def locations() -> dict:
    """List searchable locations grouped by metro corridor."""
    return {
        "corridors": locations_by_corridor(),
        "metro": default_metro_search(),
    }


# ---------------------------------------------------------------------------
# Async search
# ---------------------------------------------------------------------------


@app.post(
    "/search",
    status_code=status.HTTP_202_ACCEPTED,
    tags=["search"],
    responses={
        422: {"description": "Invalid search parameters (e.g. unknown source)."}
    },
)
def submit_search(req: SearchRequest, response: Response) -> JobAccepted:
    """
    Enqueue an apartment search and return immediately with a job id.

    The scrape runs in the background; poll GET /search/{job_id} for the
    result, or supply ``callback_url`` to receive it via webhook.
    """
    # Validate sources up front so bad input fails fast (422), not inside the
    # background job where the caller would never see it.
    try:
        normalize_sources(req.sources)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    params = {
        "price_min": req.price_min,
        "price_max": req.price_max,
        "move_in_from": req.move_in_from,
        "neighborhoods": req.neighborhoods,
        "metro": req.metro,
        "only_flexible": req.only_flexible,
        "max_pages": req.max_pages,
        "sources": req.sources,
    }
    callback = str(req.callback_url) if req.callback_url else None
    job = enqueue_search(_store, params, callback)

    status_url = f"/search/{job.id}"
    response.headers["Location"] = status_url
    return JobAccepted(job_id=job.id, status=job.status, status_url=status_url)


@app.get(
    "/search/{job_id}",
    tags=["search"],
    responses={404: {"description": "No job with that id."}},
)
def get_search(job_id: str) -> JobView:
    """Return the status (and, when finished, the results) of a search job."""
    job = _store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_id}")
    return _to_view(job)


@app.get("/", tags=["meta"])
def root() -> dict:
    """Service banner, including the active job backend."""
    return {
        "service": "zurich-search-aggregator",
        "job_backend": get_backend_name(),
        "docs": "/docs",
    }


def main() -> None:
    """Entry point: start the API server (python -m src.aggregator.api)."""
    import os

    import uvicorn

    uvicorn.run(
        "src.aggregator.api:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
    )


if __name__ == "__main__":
    main()
