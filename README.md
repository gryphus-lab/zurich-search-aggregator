# Zurich Search Aggregator

A CLI tool and REST service that scrapes apartments across the Zurich metro region and filters them.
By default it returns **all tenancy types** (long-term and month-to-month) and **all apartment types** (furnished and unfurnished); flexible-only and furnished-only are opt-in.
Results are written to JSON (and optionally CSV).

## What it does

- Scrapes listings from supported sources (`flatfox.ch`, `homegate.ch`, `theblueground.com`, `ums.ch`).
- Filters by:
  - price range (CHF/month)
  - neighborhood(s)
  - earliest move-in date (optional)
  - flexible/month-to-month friendliness (opt-in via `--flexible`)
  - furnished only (opt-in via `--furnished`)
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

Basic run (defaults to the city quartiers, all tenancy and furnishing types):

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
- `--flexible/--all`: only month-to-month listings, or all tenancy types (default `--all`)
- `--furnished/--any-furnishing`: only furnished listings, or any furnishing (default `--any-furnishing`)
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

Example (narrow to furnished, month-to-month only):

```bash
python -m src.aggregator.main --min 1700 --max 3000 --flexible --furnished
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
- `POST /search` - submit a search job (async); returns `202` + `job_id`.
- `GET /search/{job_id}` - poll job status; includes results when done.
- Interactive docs at `GET /docs` (OpenAPI/Swagger UI).

### Async search (submit + poll)

A metro-wide scrape can take minutes, so a search is **dispatched as a job**
rather than held on the HTTP request. `POST /search` returns immediately with a
`job_id`; poll `GET /search/{job_id}` until `status` is `done` (or `error`).

```bash
# 1) Submit - returns 202 Accepted with a job id
curl -X POST http://localhost:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"metro": true, "price_min": 1700, "price_max": 3500,
       "sources": ["flatfox", "homegate"]}'
# -> {"job_id": "ab12...", "status": "pending", "status_url": "/search/ab12..."}

# 2) Poll until done
curl http://localhost:8000/search/ab12...
# -> {"status": "running", ...}  then  {"status": "done", "count": 12, "listings": [...]}
```

Job status is one of `pending`, `running`, `done`, `error`. Unknown job id
returns `404`.

### Webhook callback (optional)

Instead of polling, pass a `callback_url` and the service POSTs the finished job
(status + results) to it when the search completes:

```bash
curl -X POST http://localhost:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"metro": true, "callback_url": "https://your-app.example/hook"}'
```

Request fields: `price_min`, `price_max`, `move_in_from` (YYYY-MM-DD),
`neighborhoods` (list; overrides `metro`), `metro`, `only_flexible` (default
false), `furnished_only` (default false), `max_pages`, `sources`,
`callback_url`. An unknown source returns HTTP 422 at submit time.

### Job backends (`JOB_BACKEND`)

Jobs run on one of two interchangeable backends; the API behaves identically
either way (submit/poll/callback).

- `memory` (default) - in-process thread pool. Zero dependencies, no broker.
  Great for local/dev and a single instance. Jobs are lost on restart and do
  not survive across replicas.
- `rq` - durable, out-of-process queue backed by Redis + [RQ](https://python-rq.org/),
  a lightweight, JobRunr-style option. Jobs persist in Redis and run in
  separate worker processes, so they survive API restarts and scale across
  workers.

Enable RQ:

```bash
# install the extra
uv sync --extra rq

# start Redis + an API + a worker (Docker)
JOB_BACKEND=rq docker compose --profile rq up --build

# run a worker locally (API started separately with JOB_BACKEND=rq)
JOB_BACKEND=rq REDIS_URL=redis://localhost:6379/0 \
  uv run uvicorn src.aggregator.api:app --port 8000 &
uv run rq worker --url redis://localhost:6379/0 searches
```

`GET /` reports the active `job_backend`. For a different store (e.g. Postgres
via Procrastinate, or Celery), implement the same `submit` / `get` surface and
add it to `job_backend.build_store()`.

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
