#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PORT="${PORT:-8001}"
HOST="${HOST:-0.0.0.0}"
PY="${PYTHON_BIN:-/opt/anaconda3/bin/python3}"
if [ ! -x "$PY" ]; then
  PY="$(command -v python3)"
fi

if [ "${1:-}" = "--dev" ]; then
  echo "Starting AgencyBD Enterprise in DEV mode (API :$PORT + Vite HMR :5173)..."
  lsof -ti ":$PORT" | xargs kill -9 2>/dev/null || true
  lsof -ti :5173 | xargs kill -9 2>/dev/null || true
  "$PY" -m uvicorn api:app --host "$HOST" --port "$PORT" &
  API_PID=$!
  trap 'kill $API_PID 2>/dev/null || true' EXIT
  cd "$ROOT_DIR/frontend"
  npm run dev -- --host "$HOST" --port 5173
  exit 0
fi

# Unified Production Mode: build frontend/dist if missing or --build passed, then serve everything on :$PORT
if [ "${1:-}" = "--build" ] || [ ! -f "$ROOT_DIR/frontend/dist/index.html" ]; then
  echo "Building unified frontend bundle (frontend/dist)..."
  (cd "$ROOT_DIR/frontend" && npm run build)
fi

echo "Starting unified AgencyBD Enterprise on http://localhost:$PORT ..."
lsof -ti ":$PORT" | xargs kill -9 2>/dev/null || true
exec "$PY" -m uvicorn api:app --host "$HOST" --port "$PORT"
