# src/aggregator/main.py
import typer
from datetime import date, datetime  # for date parsing if needed
from pathlib import Path
from typing import Optional, List

from rich.console import Console
from rich.table import Table

from .models import ApartmentListing
from .scrapers import run_all_scrapers
from .filters import apply_filters
from .logger import logger  # standard logger

app = typer.Typer(
    name="zurich-apartment-aggregator",
    help="Find month-to-month serviced apartments in Oerlikon, Seebach, Wipkingen, Altstetten",
    add_completion=False,
)

console = Console()


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
    neighborhoods: List[str] = typer.Option(
        ["Oerlikon", "Seebach", "Wipkingen", "Altstetten"],
        "--neigh",
        "-n",
        help="Neighborhoods to search (space-separated)",
    ),
    only_flexible: bool = typer.Option(
        True,
        "--flexible/--all",
        help="Show only month-to-month friendly listings (recommended)",
    ),
    output_json: Path = typer.Option(
        "results/latest.json", "--json", "-j", help="Path to save JSON results"
    ),
    export_csv: bool = typer.Option(False, "--csv", help="Also export as CSV"),
    max_pages: int = typer.Option(
        5, "--pages", help="Max pages per neighborhood on Immoscout"
    ),
):
    """
    Run the CLI search for short-term, furnished apartments in specified Zurich neighborhoods and present/save filtered results.

    Filters listings by price, move-in date, neighborhoods and month-to-month friendliness, deduplicates results, writes JSON to the provided path (creating parent directories), optionally exports a CSV, and prints a summary table to the console.

    Parameters:
        move_in_from (Optional[str]): Earliest move-in date in `YYYY-MM-DD` format; if provided and invalid, the command exits with code 1.
        output_json (Path): File path to write JSON results; parent directories will be created if necessary.
        export_csv (bool): If true, also write a CSV file alongside the JSON.
        max_pages (int): Maximum pages to scrape per neighborhood on Immoscout.
    """

    # Convert string date to datetime.date if provided
    move_in_date: Optional[date] = None
    if move_in_from:
        try:
            move_in_date = datetime.strptime(move_in_from, "%Y-%m-%d").date()
        except ValueError:
            console.print(
                f"[red]Invalid date format: {move_in_from}. Use YYYY-MM-DD[/red]"
            )
            raise typer.Exit(code=1)

    logger.info(
        f"Starting search with parameters: price_min={price_min}, price_max={price_max}, move_in_from={move_in_date}, neighborhoods={neighborhoods}, only_flexible={only_flexible}, max_pages={max_pages}"
    )

    # === 1. Scrape all sources ===
    raw_listings: List[ApartmentListing] = run_all_scrapers(
        price_min=price_min,
        price_max=price_max,
        neighborhoods=neighborhoods,
        move_in_from=move_in_date,
        max_pages=max_pages,
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

    # === 3. Save results ===
    output_json.parent.mkdir(parents=True, exist_ok=True)

    with open(output_json, "w", encoding="utf-8") as f:
        json_data = [
            apt.model_dump(mode="json") for apt in filtered
        ]  # This works fine with Pydantic + date
        import json

        json.dump(
            json_data, f, indent=2, ensure_ascii=False, default=str
        )  # fallback for any edge cases

    logger.info(f"💾 Saved to {output_json}")

    if export_csv:
        import pandas as pd

        df = pd.DataFrame([apt.model_dump(mode="json") for apt in filtered])
        csv_path = output_json.with_suffix(".csv")
        df.to_csv(csv_path, index=False)
        logger.info(f"📊 Also exported CSV → {csv_path}")

    # === 4. Pretty table ===
    if filtered:
        table = Table(title="Top Matches", show_lines=True)
        table.add_column("Source", style="cyan", width=12)
        table.add_column("Title", style="magenta", width=40)
        table.add_column("Price", justify="right", style="green")
        table.add_column("Neighborhood", style="blue")
        table.add_column("Available", style="yellow")
        table.add_column("Link", style="dim", width=50)

        for apt in filtered[:15]:
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
    else:
        console.print("[yellow]No matches found with current filters.[/yellow]")


# For direct execution (python -m src.aggregator.main)
if __name__ == "__main__":
    app()
