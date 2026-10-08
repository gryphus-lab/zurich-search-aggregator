# src/aggregator/main.py
import typer
from datetime import date, datetime
from pathlib import Path
from typing import Optional, List

from rich.console import Console
from rich.table import Table

from .export import write_csv, write_json
from .models import ApartmentListing
from .scrapers import AVAILABLE_SOURCES, normalize_sources, run_all_scrapers
from .filters import apply_filters
from .locations import default_metro_search, default_zurich_quartiers
from .logger import logger

app = typer.Typer(
    name="zurich-apartment-aggregator",
    help=(
        "Find apartments across the Zurich metro region. Defaults to the city "
        "quartiers (Oerlikon, Seebach, Wipkingen, Altstetten); pass --metro to "
        "search the whole metro region, or --neigh to target specific locations."
    ),
    add_completion=False,
)

console = Console()


def _resolve_locations(neighborhoods: Optional[List[str]], metro: bool) -> List[str]:
    """Pick the search locations: explicit list, else metro or city default."""
    if neighborhoods is not None:
        return neighborhoods
    return default_metro_search() if metro else default_zurich_quartiers()


def _resolve_sources_or_exit(sources: Optional[List[str]]) -> List[str]:
    """Validate the requested sources, exiting with code 1 on an unknown name."""
    try:
        return normalize_sources(sources)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)


def _parse_move_in_or_exit(move_in_from: Optional[str]) -> Optional[date]:
    """Parse a YYYY-MM-DD string to a date, exiting with code 1 if malformed."""
    if not move_in_from:
        return None
    try:
        return datetime.strptime(move_in_from, "%Y-%m-%d").date()
    except ValueError:
        console.print(f"[red]Invalid date format: {move_in_from}. Use YYYY-MM-DD[/red]")
        raise typer.Exit(code=1)


def _save_results(
    listings: List[ApartmentListing], output: Path, export_json: bool
) -> None:
    """
    Write results to ``output`` as CSV (the default). When ``export_json`` is
    set, also write a JSON file (full fidelity) with the same stem.
    """
    write_csv(listings, output)
    logger.info(f"💾 Saved CSV to {output}")

    if export_json:
        json_path = output.with_suffix(".json")
        write_json(listings, json_path)
        logger.info(f"🧾 Also exported JSON → {json_path}")


def _render_table(listings: List[ApartmentListing]) -> None:
    """Print a Rich table of the top matches, or a 'no matches' notice."""
    if not listings:
        console.print("[yellow]No matches found with current filters.[/yellow]")
        return

    table = Table(title="Top Matches", show_lines=True)
    table.add_column("Source", style="cyan", width=12)
    table.add_column("Title", style="magenta", width=40)
    table.add_column("Price", justify="right", style="green")
    table.add_column("Neighborhood", style="blue")
    table.add_column("Available", style="yellow")
    table.add_column("Link", style="dim", width=50)

    for apt in listings[:15]:
        avail = str(apt.available_from) if apt.available_from else "—"
        link_short = apt.link[:47] + "..." if len(apt.link) > 50 else apt.link
        table.add_row(
            apt.source,
            apt.title[:65],
            f"CHF {apt.price_chf:,.0f}",
            apt.neighborhood,
            avail,
            link_short,
        )

    console.print(table)


def _main_impl(
    price_min: int = 1700,
    price_max: int = 3000,
    move_in_from: Optional[str] = None,
    neighborhoods: Optional[List[str]] = None,
    only_flexible: bool = False,
    furnished_only: bool = False,
    output: Path = Path("results/latest.csv"),
    export_json: bool = False,
    max_pages: int = 5,
    metro: bool = False,
    sources: Optional[List[str]] = None,
) -> None:
    """
    Run the CLI search for apartments across the Zurich metro region and present/save filtered results.

    Filters listings by price, move-in date, locations and month-to-month friendliness, deduplicates results, writes CSV to the provided path (creating parent directories), optionally also writes JSON, and prints a summary table to the console.

    Parameters:
        price_min (int): Minimum monthly rent in CHF.
        price_max (int): Maximum monthly rent in CHF.
        move_in_from (Optional[str]): Earliest move-in date in `YYYY-MM-DD` format; if provided and invalid, the command exits with code 1.
        neighborhoods (Optional[List[str]]): Locations to search. When None, defaults to the city quartiers, or the full metro region when `metro` is True.
        only_flexible (bool): If True, keep only month-to-month friendly listings. Defaults to False (all tenancy types).
        furnished_only (bool): If True, restrict to furnished listings. Defaults to False (furnished and unfurnished).
        output (Path): File path to write CSV results; parent directories will be created if necessary.
        export_json (bool): If true, also write a JSON file (same stem, full fidelity).
        max_pages (int): Maximum result pages to scrape per location.
        metro (bool): When True and no explicit neighborhoods are given, search the whole Zurich metro region.
        sources (Optional[List[str]]): Which aggregators to query (any of
            flatfox, blueground, homegate, ums). When None or empty, all run.
            An unknown source name exits with code 1.
    """
    neighborhoods = _resolve_locations(neighborhoods, metro)
    selected_sources = _resolve_sources_or_exit(sources)
    move_in_date = _parse_move_in_or_exit(move_in_from)

    logger.info(
        f"Starting search with parameters: price_min={price_min}, price_max={price_max}, move_in_from={move_in_date}, neighborhoods={neighborhoods}, sources={selected_sources}, only_flexible={only_flexible}, furnished_only={furnished_only}, max_pages={max_pages}"
    )

    # === 1. Scrape selected sources ===
    raw_listings: List[ApartmentListing] = run_all_scrapers(
        price_min=price_min,
        price_max=price_max,
        neighborhoods=neighborhoods,
        move_in_from=move_in_date,
        max_pages=max_pages,
        sources=selected_sources,
        furnished_only=furnished_only,
    )

    # === 2. Apply filters + deduplication ===
    filtered: List[ApartmentListing] = (
        apply_filters(
            listings=raw_listings,
            price_min=price_min,
            price_max=price_max,
            move_in_from=move_in_date,
            neighborhoods=neighborhoods,
            only_month_to_month=only_flexible,
        )
        or []
    )
    logger.info(f"Filtering complete: {len(filtered)} listings match criteria")

    # === 3. Save results + render ===
    _save_results(filtered, output, export_json)
    _render_table(filtered)


@app.command()
def main(
    price_min: int = typer.Option(
        1700, "--min", "-m", help="Minimum monthly rent in CHF"
    ),
    price_max: int = typer.Option(
        3000, "--max", "-M", help="Maximum monthly rent in CHF"
    ),
    move_in_from: Optional[str] = typer.Option(
        None, "--move-in", "-d", help="Earliest move-in date (YYYY-MM-DD)"
    ),
    neighborhoods: Optional[List[str]] = typer.Option(
        None,
        "--neigh",
        "-n",
        help=(
            "Locations to search (space-separated). Defaults to the city "
            "quartiers, or the full metro region when --metro is set."
        ),
    ),
    metro: bool = typer.Option(
        False,
        "--metro",
        help=(
            "Search the whole Zurich metro region (all corridors) instead of "
            "only the city quartiers. Ignored when --neigh is given."
        ),
    ),
    sources: Optional[List[str]] = typer.Option(
        None,
        "--source",
        "-s",
        help=(
            "Aggregator(s) to query (repeatable): "
            f"{', '.join(AVAILABLE_SOURCES)}. Defaults to all."
        ),
    ),
    only_flexible: bool = typer.Option(
        False,
        "--flexible/--all",
        help="Only month-to-month friendly listings (--flexible), or all tenancy types (--all, default)",
    ),
    furnished_only: bool = typer.Option(
        False,
        "--furnished/--any-furnishing",
        help="Only furnished listings (--furnished), or furnished and unfurnished (--any-furnishing, default)",
    ),
    output: Path = typer.Option(
        "results/latest.csv",
        "--out",
        "-o",
        help="Path to save CSV results (default format)",
    ),
    export_json: bool = typer.Option(
        False, "--json", help="Also export JSON (full fidelity) alongside the CSV"
    ),
    max_pages: int = typer.Option(
        5, "--pages", help="Max result pages to scrape per location"
    ),
) -> None:
    """Typer CLI wrapper for the main function."""
    _main_impl(
        price_min=price_min,
        price_max=price_max,
        move_in_from=move_in_from,
        neighborhoods=neighborhoods,
        only_flexible=only_flexible,
        furnished_only=furnished_only,
        output=output,
        export_json=export_json,
        max_pages=max_pages,
        metro=metro,
        sources=sources,
    )


# For direct execution (python -m src.aggregator.main)
if __name__ == "__main__":
    app()
