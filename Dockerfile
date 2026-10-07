# Zurich Search Aggregator - FastAPI service that scrapes/filters apartments.
#
# Built on the official uv image (Python 3.14 + uv preinstalled). Chromium and
# its OS dependencies are installed with `playwright install --with-deps`,
# mirroring the local `mise bootstrap` flow. Runs as a non-root user.

FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Keep uv deterministic and copy (not symlink) into the image layer.
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    # Install Playwright browsers into a stable, image-wide location.
    PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers

WORKDIR /app

# Create an unprivileged user to run the service (avoids running as root).
RUN useradd --create-home --uid 10001 appuser

# 1) Install third-party dependencies first (cached unless the lockfile
#    changes). --frozen pins resolved versions from uv.lock; --no-build avoids
#    executing dependency setup scripts; --no-install-project defers our own
#    package until the source is copied. README.md is copied because
#    pyproject's `readme` field references it.
# The `rq` extra is included so the same image can run either the API or an
# RQ worker (docker compose --profile rq).
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-build --no-install-project --extra rq

# 2) Install Chromium + its system libraries via Playwright (needs root for
#    apt). --no-project avoids building our package before the source exists.
#    Browsers live in PLAYWRIGHT_BROWSERS_PATH so they survive the USER switch.
RUN uv run --no-dev --no-project --no-build playwright install --with-deps chromium

# 3) Copy the application source, install our package, create the results dir,
#    and hand ownership to the unprivileged user. Only our own (trusted) package
#    is built here; all third-party deps were installed with --no-build above.
COPY src ./src
RUN uv sync --frozen --no-dev --extra rq \
    && mkdir -p /app/results \
    && chown -R appuser:appuser /app /opt/pw-browsers

VOLUME ["/app/results"]

# Run as a long-lived REST service (FastAPI + uvicorn) on port 8000.
ENV HOST=0.0.0.0 \
    PORT=8000 \
    PATH="/app/.venv/bin:${PATH}"
EXPOSE 8000
USER appuser

# POST /search runs a scrape; GET /health, /sources, /locations are metadata.
# Invokes the pre-synced venv directly (no runtime dependency resolution).
# The one-shot CLI is still available via:
#   docker run --rm --entrypoint python <image> -m src.aggregator.main --metro
ENTRYPOINT ["uvicorn", "src.aggregator.api:app", "--host", "0.0.0.0", "--port", "8000"]
