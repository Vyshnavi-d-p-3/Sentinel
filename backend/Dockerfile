# syntax=docker/dockerfile:1.7

# ---------- Stage 1: build ----------------------------------------------------
# Compile wheels in a fat image so the runtime stage can stay slim. We split
# requirements into its own layer so dependency installs are cached when only
# application code changes.
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libpq-dev \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip wheel --wheel-dir /build/wheels -r requirements.txt

# ---------- Stage 2: runtime --------------------------------------------------
# Minimal runtime image. Runs as a dedicated unprivileged user, exposes a
# health-check, and has only the runtime libpq (no toolchain).
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SENTINEL_LOG_FORMAT=json \
    PORT=8000

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
        tini \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 1001 sentinel \
 && useradd  --system --uid 1001 --gid sentinel --home-dir /app --shell /sbin/nologin sentinel

COPY --from=builder /build/wheels /tmp/wheels
COPY requirements.txt .
RUN pip install --no-index --find-links=/tmp/wheels -r requirements.txt \
 && rm -rf /tmp/wheels

# Copy the app last so code changes don't bust the dependency cache.
COPY --chown=sentinel:sentinel . .

USER sentinel
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl --fail --silent http://127.0.0.1:${PORT}/livez || exit 1

# ``tini`` is PID 1 so signals (SIGTERM from Kubernetes / docker stop) reach
# uvicorn cleanly and in-flight requests can drain.
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
