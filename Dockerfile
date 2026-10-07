# Zurich Search Aggregator - CLI that scrapes/filters apartments via Playwright.
#
# Built on the official uv image (Python 3.14 + uv preinstalled). Chromium and
# its OS dependencies are installed with `playwright install --with-deps`,
# mirroring the local `mise bootstrap` flow.

FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Keep uv deterministic and copy (not symlink) into the image layer.
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    # Install Playwright browsers into a stable, image-wide location.
    PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers

WORKDIR /app

# 1) Install Python dependencies first (cached unless the lockfile changes).
#    --no-install-project installs only third-party deps, not our package yet.
#    README.md is copied too because pyproject's `readme` field references it.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# 2) Install Chromium + its system libraries via Playwright.
#    --no-project avoids building our package before the source is present.
RUN uv run --no-dev --no-project playwright install --with-deps chromium

# 3) Copy the application source and install the project itself.
COPY src ./src
RUN uv sync --frozen --no-dev

# Results are written here; declare it so it can be mounted/persisted.
RUN mkdir -p /app/results
VOLUME ["/app/results"]

# Default entrypoint runs the aggregator CLI; args pass straight through,
# e.g.  docker run --rm zurich-search-aggregator:latest --metro --min 1700
ENTRYPOINT ["uv", "run", "--no-dev", "python", "-m", "src.aggregator.main"]
CMD ["--help"]
