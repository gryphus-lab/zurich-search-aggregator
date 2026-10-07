# syntax=docker/dockerfile:1

# Build dependencies and the application wheel in an isolated stage.
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Dependency metadata changes less often than application code, so this layer
# remains cached when only source files change.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-build --no-install-project --extra rq

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra rq --no-editable

# Optional CI target. The default build stops at the runtime stage below.
FROM builder AS test
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --extra rq --no-editable
COPY tests ./tests
COPY mise.toml ./mise.toml
RUN uv run --frozen pytest -q

# Keep the production image free of uv, build metadata, and application source.
FROM python:3.14-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
    HOST=0.0.0.0 \
    PORT=8000 \
    PATH=/app/.venv/bin:$PATH

WORKDIR /app

# Install only the browser and OS libraries required by Playwright, then
# remove apt indexes to reduce the final layer size.
COPY --from=builder /app/.venv /app/.venv
RUN python -m playwright install --with-deps --only-shell chromium \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/results \
    && chown -R appuser:appuser /app /opt/pw-browsers

VOLUME ["/app/results"]
EXPOSE 8000
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

ENTRYPOINT ["uvicorn", "aggregator.api:app", "--host", "0.0.0.0", "--port", "8000"]
