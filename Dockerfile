# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1: build a wheel from the source tree.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS build

WORKDIR /src
RUN pip install --no-cache-dir build

COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m build --wheel --outdir /dist

# ---------------------------------------------------------------------------
# Stage 2: minimal runtime image with the API and SDK extras installed.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Deterministic, production-friendly Python defaults.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    MEETING_MEMORY_DB=/data/meeting-memory.db \
    MEETING_MEMORY_HOST=0.0.0.0 \
    MEETING_MEMORY_PORT=8000

WORKDIR /app

COPY --from=build /dist/*.whl /tmp/
RUN WHEEL="$(ls /tmp/*.whl)" \
    && pip install --no-cache-dir "${WHEEL}[api,sdk]" \
    && rm -f /tmp/*.whl

COPY scripts/start.sh scripts/healthcheck.py /app/scripts/
RUN chmod +x /app/scripts/start.sh

# Run as an unprivileged user and persist the database on a mounted volume.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /data /app
USER appuser

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "/app/scripts/healthcheck.py"]

ENTRYPOINT ["/app/scripts/start.sh"]
