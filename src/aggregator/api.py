"""
REST API for the Zurich Search Aggregator.

Exposes the same search parameters as the CLI over HTTP so the aggregator can
run as a long-lived service. The blocking, Playwright-backed search runs in a
threadpool to avoid clashing with the async event loop.

Run with:  uvicorn src.aggregator.api:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from .locations import default_metro_search, locations_by_corridor
from .models import ApartmentListing
from .scrapers import AVAILABLE_SOURCES
from .service import resolve_neighborhoods, search_apartments

app = FastAPI(
    title="Zurich Search Aggregator",
    description=(
        "Search apartments across the Zurich metro region from multiple "
        "aggregators (Flatfox, Blueground, Homegate, UMS)."
    ),
    version="0.1.0",
)


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


class SearchResponse(BaseModel):
    count: int
    neighborhoods: List[str]
    sources: List[str]
    listings: List[ApartmentListing]


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


@app.post("/search", response_model=SearchResponse, tags=["search"])
async def search(req: SearchRequest) -> SearchResponse:
    """
    Run an apartment search and return the filtered listings.

    The underlying scrape is blocking (Playwright sync API), so it runs in a
    threadpool to keep the event loop responsive.
    """
    try:
        listings = await run_in_threadpool(
            search_apartments,
            price_min=req.price_min,
            price_max=req.price_max,
            move_in_from=req.move_in_from,
            neighborhoods=req.neighborhoods,
            metro=req.metro,
            only_flexible=req.only_flexible,
            max_pages=req.max_pages,
            sources=req.sources,
        )
    except ValueError as exc:
        # e.g. unknown source name
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return SearchResponse(
        count=len(listings),
        neighborhoods=resolve_neighborhoods(req.neighborhoods, req.metro),
        sources=req.sources or AVAILABLE_SOURCES,
        listings=listings,
    )


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
