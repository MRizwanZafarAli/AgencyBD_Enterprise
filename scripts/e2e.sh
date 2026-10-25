#!/usr/bin/env bash
# End-to-end tests: builds the web app, starts the API on a throwaway database (port 8011) and runs Playwright with the installed Chrome.
set -euo pipefail
cd "$(dirname "$0")/.."
TMP="$(mktemp -d)"
trap 'kill ${API_PID:-0} 2>/dev/null || true; rm -rf "$TMP"' EXIT
export DB_PATH="$TMP/e2e.db" AGENCYBD_SKIP_DOTENV=1 AGENCYBD_ENV=test
(cd frontend && npm run build >/dev/null)
KEY=$(python3 scripts/create_admin_key.py --name e2e 2>/dev/null | sed -n 's/^API key.*: //p')
python3 -m uvicorn api:app --port 8011 --log-level warning &
API_PID=$!
for _ in $(seq 1 40); do curl -sf localhost:8011/healthz/live >/dev/null && break; sleep 0.5; done
cd frontend && E2E_KEY="$KEY" npx playwright test "$@"
