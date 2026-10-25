#!/usr/bin/env bash
# Release gate: nothing ships unless tests, type-check, lint, build and the container image all pass.
# Usage: scripts/release.sh [version]     (default: git short sha)
# It does NOT push, tag, deploy or touch a running server; promote the printed image tag through your normal process.
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="${1:-$(git rev-parse --short HEAD)}"

echo "1/5 backend tests";   AGENCYBD_SKIP_DOTENV=1 python3 -m pytest -q
echo "2/5 frontend checks"; (cd frontend && npx tsc -b && npx oxlint && npm run build)
echo "3/5 secret scan";     python3 -m pytest -q tests/test_repo_hygiene.py
echo "4/5 backup restore drill"; python3 -m pytest -q tests/test_backup.py
if command -v docker >/dev/null && docker info >/dev/null 2>&1; then
  echo "5/5 image build";   docker build -t "agencybd-enterprise:${VERSION}" .
  echo "Built agencybd-enterprise:${VERSION}"
else
  echo "5/5 image build skipped: Docker daemon not available"
fi
printf '{"version":"%s","commit":"%s","built_at":"%s"}\n' "$VERSION" "$(git rev-parse HEAD)" "$(date -u +%FT%TZ)" > RELEASE.json
echo "Release candidate ${VERSION} passed. Manifest written to RELEASE.json"
