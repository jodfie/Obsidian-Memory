# Multi-stage Dockerfile for Obsidian-Memory Backend
# Supports both dev and prod targets

# ============================================================================
# Builder stage (shared)
# ============================================================================
FROM python:3.12-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY backend/pyproject.toml ./

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e ".[dev]"

# ============================================================================
# Development stage
# ============================================================================
FROM python:3.12-slim as dev

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy from builder (includes dev dependencies)
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY backend/ ./backend/
COPY backend/pyproject.toml ./

# Copy entrypoint script
COPY docker-entrypoint.sh /app/docker-entrypoint.sh

# Install application
RUN pip install --no-cache-dir -e ".[dev]"

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app && \
    chmod +x /app/docker-entrypoint.sh

USER appuser

# Expose port
EXPOSE 8765

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8765/health || exit 1

# Development entrypoint (hot reload)
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8765", "--reload"]

# ============================================================================
# Production stage
# ============================================================================
FROM python:3.12-slim as prod

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy from builder (production dependencies only)
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY backend/ ./backend/
COPY backend/pyproject.toml ./

# Copy entrypoint script
COPY docker-entrypoint.sh /app/docker-entrypoint.sh

# Install application in production mode (without dev dependencies)
RUN pip install --no-cache-dir -e "." --no-deps && \
    pip install --no-cache-dir fastapi uvicorn[standard] pydantic pydantic-settings \
    python-frontmatter aiosqlite aiofiles anthropic pyyaml psutil

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app && \
    chmod +x /app/docker-entrypoint.sh

USER appuser

# Expose port
EXPOSE 8765

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8765/health || exit 1

# Production entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8765", "--workers", "2"]
