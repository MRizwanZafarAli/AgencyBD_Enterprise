#!/usr/bin/env bash
# ==============================================================================
# AgencyBD_Enterprise: Production Deployment & Health Sentry Script
# ==============================================================================

set -e

echo "=========================================================="
echo "⚡ Starting AgencyBD Enterprise Production Deployment..."
echo "=========================================================="

# 1. Environment Verification
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Bootstrapping from .env.example..."
    cp .env.example .env
fi

# 2. Database Migration & Security Initialization
echo "🔒 Initializing database and verifying cryptographic vaults..."
python3 -c "from database.db import init_db; init_db(); print('✅ Database WAL Mode and Tables Initialized.')"

# 3. Execute Pre-flight Test Suite
echo "🧪 Running pre-flight automated test suites..."
PYTHONPATH=. pytest tests/test_auth_rbac.py tests/test_webhooks.py tests/test_api_endpoints.py -q
echo "✅ Pre-flight security & API tests passed!"

# 4. Display Operational Ports
echo "=========================================================="
echo "🚀 Enterprise Swarm Ready for High-Ticket B2B Acquisition!"
echo "   • FastAPI REST Engine: http://localhost:8001 (Docs at /docs)"
echo "   • Prometheus Telemetry: http://localhost:8001/metrics"
echo "   • Streamlit Command Center: http://localhost:8502"
echo "   • Containerized Deployment: docker compose up -d"
echo "=========================================================="
