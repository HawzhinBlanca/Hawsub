# Hawsub Production Workstation Dockerfile
# Multi-stage build with security hardening.

# ============================================================
# Stage 1: Builder — Install dependencies
# ============================================================
FROM python:3.11.9-slim AS builder

WORKDIR /app

# Install build dependencies & ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project definition first (layer caching)
COPY pyproject.toml README.md ./

# Copy source code
COPY hawsub/ ./hawsub/
COPY config/ ./config/
COPY tests/gold/ ./tests/gold/

# Install Hawsub system
RUN pip install --no-cache-dir .

# ============================================================
# Stage 2: Production Runner — Minimal attack surface
# ============================================================
FROM python:3.11.9-slim AS runner

LABEL maintainer="Hawsub Team"
LABEL description="Hawsub — Cinema-grade English to Sorani Kurdish subtitle localization"
LABEL version="1.0.0"

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd --gid 1001 hawsub && \
    useradd --uid 1001 --gid 1001 --create-home --shell /bin/bash hawsub

# Copy installed packages and app from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/hawsub /usr/local/bin/hawsub
COPY --from=builder /app /app

# Create output directory with correct permissions
RUN mkdir -p /app/output /app/logs && \
    chown -R hawsub:hawsub /app

# Switch to non-root user
USER hawsub

EXPOSE 8080

# Environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV HAWSUB_LOG_DIR=/app/logs

# Health check — verify the API is responding
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

CMD ["hawsub", "gui", "--port", "8080"]
