# Hawsub Production Workstation Dockerfile
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies & ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project definition
COPY pyproject.toml README.md ./
COPY hawsub/ ./hawsub/
COPY config/ ./config/
COPY tests/gold/ ./tests/gold/

# Install Hawsub system
RUN pip install --no-cache-dir .

# Production runner stage
FROM python:3.11-slim AS runner

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/hawsub /usr/local/bin/hawsub
COPY --from=builder /app /app

EXPOSE 8080

ENV PYTHONUNBUFFERED=1

CMD ["hawsub", "gui", "--port", "8080"]
