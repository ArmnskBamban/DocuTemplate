# Multi-stage build for PraktiKit backend
# Stage 1: Builder - install dependencies
FROM python:3.11-slim as builder

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies into /app/.venv
RUN uv sync --no-dev

# Stage 2: Runtime - minimal production image
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies for python-docx (libxml2, libxslt)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libxml2 \
    libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY src/ /app/src/

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TEMP_DIRECTORY=/tmp/praktikit \
    LOG_LEVEL=INFO

# Create temp directory
RUN mkdir -p /tmp/praktikit && chmod 1777 /tmp/praktikit

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()"

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "praktikit.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
