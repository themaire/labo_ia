# ─── Build stage ────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# System deps needed to compile opencv-python and psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY flask_ticket/requirements.txt ./requirements.txt

# Install Python dependencies into a dedicated prefix so we can copy them later
RUN pip install --prefix=/install --no-cache-dir gunicorn -r requirements.txt

# ─── Runtime stage ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Runtime shared libs required by OpenCV and psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for security
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY flask_ticket/ ./flask_ticket/

# Persistent volume for uploaded files
RUN mkdir -p uploads && chown appuser:appgroup uploads

# Gunicorn configuration
COPY gunicorn.conf.py ./gunicorn.conf.py

USER appuser

EXPOSE 5000

CMD ["gunicorn", "--config", "gunicorn.conf.py", "flask_ticket.app:app"]
