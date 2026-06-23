FROM python:3.11-slim AS base

# Install OS packages: build tools + gosu for clean privilege drop
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user (uid/gid 1001)
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid 1001 --no-create-home --shell /bin/false appuser

WORKDIR /app

# Install Python dependencies as root (needs write access to site-packages)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Train the ML model at build time (runs as root; artefacts are chowned below)
RUN python -m ml.train

# Create data directory and hand over ownership of everything to appuser
RUN mkdir -p /app/data && \
    chown -R appuser:appgroup /app

# Copy and register the entrypoint (must be owned/executable by root for gosu to work)
COPY scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Expose application port
EXPOSE 8000

# Healthcheck using curl (installed above)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Entrypoint drops to appuser after fixing volume permissions
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--proxy-headers"]
