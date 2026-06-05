# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

# Install uv (fast Python package installer used by this project)
RUN pip install --no-cache-dir uv

WORKDIR /build

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock* ./

# Install all runtime deps into an isolated prefix so we can copy them cleanly
RUN uv pip install --system --no-cache \
    "pydantic>=2.0" \
    "PyYAML>=6.0" \
    "fastapi>=0.110" \
    "sqlalchemy>=2.0" \
    "uvicorn>=0.29.0" \
    "python-dotenv>=1.0" \
    "httpx>=0.27" \
    "aiofiles>=23.0"

# If uv.lock exists, do a full locked install on top
RUN if [ -f uv.lock ]; then uv pip install --system --no-cache -r <(uv export --no-dev 2>/dev/null || true) 2>/dev/null || true; fi

# Copy the full source after deps are cached
COPY . .

# Install the package itself (editable-like, but build-based for prod)
RUN uv pip install --system --no-cache -e . 2>/dev/null || pip install --no-cache-dir -e .


# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Non-root user for security
RUN addgroup --system dpi && adduser --system --ingroup dpi dpi

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source
COPY --chown=dpi:dpi . .

# Create a writable directory for SQLite (Railway provides ephemeral FS;
# for persistent storage point DATABASE_URL at a Postgres Railway service)
RUN mkdir -p /app/data && chown dpi:dpi /app/data

# Copy and set up start script
COPY --chown=dpi:dpi start.sh /app/start.sh
RUN chmod +x /app/start.sh

USER dpi

# Railway injects $PORT at runtime; uvicorn reads it via start.sh
EXPOSE 8000

# Health check so Railway knows when the container is live
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/healthz')" || exit 1

CMD ["/app/start.sh"]