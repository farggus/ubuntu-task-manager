# Build stage
FROM python:3.12-slim-bookworm AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# Final stage
FROM python:3.12-slim-bookworm

LABEL org.opencontainers.image.title="Ubuntu Task Manager" \
      org.opencontainers.image.description="TUI dashboard for monitoring and managing Linux servers" \
      org.opencontainers.image.version="2.0.0" \
      org.opencontainers.image.source="https://github.com/farggus/ubuntu-task-manager" \
      org.opencontainers.image.licenses="MIT"

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LOG_DEST=stdout \
    LOG_FORMAT=json \
    PYTHONPATH=/app/src \
    # Textual configuration
    TERM=xterm-256color

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    procps \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN groupadd --gid 1000 utm \
    && useradd --uid 1000 --gid utm --shell /bin/bash --create-home utm

# Copy wheels and install
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache /wheels/* \
    && rm -rf /wheels

# Copy application code
COPY --chown=utm:utm . .

# Create necessary directories
RUN mkdir -p logs cache \
    && chown -R utm:utm /app

# Switch to non-root user
USER utm

# Healthcheck - verify Python process is running
# For TUI apps, we check if the main module can be imported
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.path.insert(0, 'src'); from collectors import system; print('OK')" || exit 1

# Note: This application requires access to system resources.
# Run with: docker run -it --pid=host -v /var/run/docker.sock:/var/run/docker.sock utm
# For docker socket access, add user to docker group or run with --group-add

ENTRYPOINT ["python", "src/main.py"]
