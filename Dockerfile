# Build stage
FROM python:3.12-slim-bookworm as builder

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

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LOG_DEST=stdout \
    LOG_FORMAT=json \
    PYTHONPATH=/app/src

# Install runtime deps if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    procps \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .

RUN pip install --no-cache /wheels/*

COPY . .

# Create logs directory
RUN mkdir -p logs

# Note: This application requires access to system resources (processes, docker socket).
# It is recommended to run with:
# docker run -it --pid=host -v /var/run/docker.sock:/var/run/docker.sock ...

ENTRYPOINT ["python", "src/main.py"]