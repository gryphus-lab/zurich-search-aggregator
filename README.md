# Zurich Search Aggregator

A small CLI tool that scrapes furnished apartments in Zurich and filters them for "flexible / month-to-month"-friendly listings.
Results are written to JSON (and optionally CSV).

## What it does

- Scrapes listings from supported sources (e.g. `flatfox.ch`, `theblueground.com`).
- Filters by:
  - price range (CHF/month)
  - neighborhood(s)
  - earliest move-in date (optional)
  - flexible/month-to-month friendliness (default on)
- Deduplicates results.
- Saves output to `results/latest.json` (and `results/latest.csv` when `--csv` is set).
- Prints a Rich table of top matches to your terminal.

### Requirements

- Python dependencies (see `requirements.txt`)
- Playwright (browser binaries)

After installing Python deps, install the browser binaries:

```bash
python -m playwright install chromium
```

### Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
git config core.hooksPath .githooks
```

### Run

Basic run (defaults to neighborhoods and "flexible" filtering):

```bash
python -m src.aggregator.main --min 1700 --max 3000
```

Common options:

- `--min, -m <int>`: minimum monthly rent (CHF)
- `--max, -M <int>`: maximum monthly rent (CHF)
- `--move-in, -d <YYYY-MM-DD>`: earliest move-in date
- `--neigh, -n <neigh>...`: neighborhoods to search (space-separated)
- `--flexible/--all`: show only flexible listings (default `--flexible`)
- `--json, -j <path>`: where to write JSON (default `results/latest.json`)
- `--csv`: also export CSV beside the JSON output
- `--pages <int>`: max pages per neighborhood (currently used by scrapers where applicable)

Example (include move-in date and export CSV):

```bash
python -m src.aggregator.main \
  --min 1800 --max 2800 \
  --move-in 2026-05-01 \
  --neigh Oerlikon Seebach Wipkingen Altstetten \
  --csv
```

Example (show all listings, not just flexible):

```bash
python -m src.aggregator.main --min 1700 --max 3000 --all
```

### Output

- JSON: `results/latest.json` (configurable with `--json`)
- CSV (optional): same path with `.csv` suffix
- Logs: `results/scraper.log`

### Notes

- "Flexible" is determined heuristically by matching keywords in the listing text/snippet.
