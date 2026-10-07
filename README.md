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
- `--neigh, -n <neigh>...`: locations to search (space-separated). Overrides `--metro`.
- `--metro`: search the whole Zurich metro region (all corridors) instead of only the city quartiers
- `--source, -s <name>...`: aggregator(s) to query (repeatable). Defaults to all.
- `--flexible/--all`: show only flexible listings (default `--flexible`)
- `--json, -j <path>`: where to write JSON (default `results/latest.json`)
- `--csv`: also export CSV beside the JSON output
- `--pages <int>`: max result pages per location (used by scrapers where applicable)

### Search area

Without `--neigh`, the search defaults to the city of Zurich quartiers
(Oerlikon, Seebach, Wipkingen, Altstetten). Pass `--metro` to search the full
Zurich metro region across all corridors:

- **West (Limmattal / A1):** Schlieren, Dietikon, Urdorf, Oberengstringen, Unterengstringen, Geroldswil
- **North / North-East (Glattal):** Wallisellen, Dübendorf, Opfikon (Glattbrugg), Kloten, Wangen-Brüttisellen, Dietlikon, Volketswil
- **North-West (Furttal):** Regensdorf, Dällikon, Buchs (ZH), Otelfingen
- **South (Sihltal / Left Bank):** Adliswil, Kilchberg, Thalwil, Rüschlikon, Langnau am Albis
- **East (Gold Coast):** Zollikon, Zumikon, Küsnacht, Erlenbach

All apartment types are included (furnished and unfurnished). The location
registry lives in `src/aggregator/locations.py`; add or adjust entries there.

```bash
# Search the whole metro region
python -m src.aggregator.main --metro --min 1700 --max 3500

# Target specific metro towns
python -m src.aggregator.main --neigh Thalwil Küsnacht Adliswil
```

### Sources (aggregators)

By default all aggregators run: **flatfox**, **blueground**, **homegate**, **ums**.
Use `--source/-s` (repeatable) to query a subset:

```bash
# Only Flatfox and Homegate
python -m src.aggregator.main --source flatfox --source homegate

# Only one source, across the whole metro region
python -m src.aggregator.main --metro -s flatfox
```

An unknown source name exits with a clear error. Note that Blueground and UMS
are furnished-serviced-apartment sources and only cover the city of Zurich.

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

## REST API

The aggregator also runs as a long-lived HTTP service (FastAPI + uvicorn),
exposing the same search parameters as the CLI.

```bash
# Run locally
uv run uvicorn src.aggregator.api:app --host 0.0.0.0 --port 8000
# or: uv run python -m src.aggregator.api
```

Endpoints:

- `GET /health` - liveness probe.
- `GET /sources` - the available aggregators.
- `GET /locations` - searchable locations grouped by metro corridor.
- `POST /search` - run a search; JSON body mirrors the CLI options.
- Interactive docs at `GET /docs` (OpenAPI/Swagger UI).

```bash
# Whole metro region, Flatfox + Homegate only
curl -X POST http://localhost:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"metro": true, "price_min": 1700, "price_max": 3500,
       "sources": ["flatfox", "homegate"]}'
```

Request fields: `price_min`, `price_max`, `move_in_from` (YYYY-MM-DD),
`neighborhoods` (list; overrides `metro`), `metro`, `only_flexible`,
`max_pages`, `sources`. An unknown source returns HTTP 422.

### Docker

The image runs the REST API as a long-lived service on port 8000.

```bash
# Build the image
mise docker-build          # or: docker build -t zurich-search-aggregator:latest .

# Start the service (detached) at http://localhost:8000
mise docker-compose        # docker compose up --build -d

curl http://localhost:8000/health
docker compose down        # stop it

# Or run the image directly
docker run --rm -p 8000:8000 -v "$PWD/results:/app/results" \
  zurich-search-aggregator:latest
```

The one-shot CLI is still available from the same image:

```bash
docker run --rm -v "$PWD/results:/app/results" \
  --entrypoint uv zurich-search-aggregator:latest \
  run --no-dev python -m src.aggregator.main --metro --min 1700 --max 3500 --csv
```

### Output

- JSON: `results/latest.json` (configurable with `--json`)
- CSV (optional): same path with `.csv` suffix
- Logs: `results/scraper.log`

### Notes

- "Flexible" is determined heuristically by matching keywords in the listing text/snippet.
