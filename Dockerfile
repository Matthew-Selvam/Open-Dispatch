# ─── Stage 1: Build ──────────────────────────────────────────────────────────
# Installs all Python deps (including C-extension wheels for Pillow) into a
# dedicated virtualenv.  Build tools (gcc, libjpeg-dev, zlib1g-dev) stay here
# and never land in the final image.
FROM python:3.12-slim AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv

RUN python -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Build-time system deps (gcc for native extensions; libjpeg/zlib for Pillow)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libjpeg-dev \
        zlib1g-dev \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# ─── Stage 2: Runtime ────────────────────────────────────────────────────────
# Lean image: build tools gone, only shared libs Pillow needs at runtime.
# Runs as a non-root user (dispatch) for defence-in-depth.
FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OPEN_DISPATCH_DATA=/data \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# Runtime-only system deps:
#   curl         — used by HEALTHCHECK
#   ca-certificates — TLS for httpx / atproto
#   libjpeg62-turbo — Pillow JPEG support (the .so built against in stage 1)
#   zlib1g       — Pillow PNG/zip support
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        libjpeg62-turbo \
        zlib1g \
    && rm -rf /var/lib/apt/lists/* \
    # Non-root user for principle of least privilege
    && groupadd -r dispatch \
    && useradd -r -g dispatch --no-create-home --home /app dispatch

# Copy pre-built venv from builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy application source
COPY . .

# Ensure data dir exists and is writable by the runtime user
RUN mkdir -p /data && chown -R dispatch:dispatch /app /data

USER dispatch

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
