# Multi-Stage Production Dockerfile for AgencyBD_Enterprise
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS builder

WORKDIR /app

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final Runtime Container
FROM python:3.11-slim AS runner

WORKDIR /app

# Install runtime utilities & curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged security user (Zero-Trust Principle)
RUN groupadd -g 1001 appgroup && \
    useradd -u 1001 -g appgroup -s /bin/bash -m appuser

# Copy installed Python packages from builder
COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONPATH=/app

# Copy application source code
COPY --chown=appuser:appgroup . .
COPY --from=frontend --chown=appuser:appgroup /frontend/dist /app/frontend/dist

# Ensure data directory exists and has permissions
RUN mkdir -p /app/data /app/logs && chown -R appuser:appgroup /app/data /app/logs

USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/healthz/live || exit 1

# Default launch command: runs FastAPI backend
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8001"]
