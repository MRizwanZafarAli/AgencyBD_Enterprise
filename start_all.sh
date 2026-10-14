#!/usr/bin/env bash
# ==============================================================================
# ApexCore OS / AgencyBD_Enterprise: Master Multi-Service Launcher
# Starts FastAPI Microservice (:8001), Streamlit (:8502), and Vite React (:5173)
# ==============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "======================================================================"
echo "⚡ Starting ApexCore OS Enterprise Platform"
echo "📂 Project Root: $PROJECT_DIR"
echo "======================================================================"

# 0. First-run guard: secrets must exist (never shipped in the repo)
if [ ! -f .env ] || grep -q "^AGENCYBD_JWT_SECRET=replace" .env; then
    echo "🔐 Generating secrets (first run)..."
    python3 scripts/generate_secrets.py
    echo "   Create your first API key with: python3 scripts/create_admin_key.py"
fi

# 1. Kill any existing instances on the ports
lsof -ti:8001 | xargs kill -9 2>/dev/null || true
lsof -ti:5173 | xargs kill -9 2>/dev/null || true
if [ "$1" == "--with-streamlit" ]; then
    lsof -ti:8502 | xargs kill -9 2>/dev/null || true
fi

# 2. Start FastAPI Microservice Core (:8001)
echo "🚀 [1/2] Launching FastAPI Core REST Engine & Sovereign UI on port 8001..."
PYTHONPATH=. nohup uvicorn api:app --port 8001 --host 0.0.0.0 > logs/fastapi.log 2>&1 &
API_PID=$!
echo "   -> FastAPI PID: $API_PID"

# 3. Start Vite React 19 Frontend (:5173) for HMR development
echo "🚀 [2/2] Launching Obsidian Sovereign React UI (Vite Dev Server) on port 5173..."
cd frontend
nohup npm run dev -- --port 5173 --host 0.0.0.0 > ../logs/frontend.log 2>&1 &
FE_PID=$!
echo "   -> React Vite PID: $FE_PID"
cd ..

# Optional legacy Streamlit lab
if [ "$1" == "--with-streamlit" ]; then
    echo "🔬 Launching legacy Streamlit Python Lab on port 8502..."
    PYTHONPATH=. nohup streamlit run app.py --server.port 8502 --server.headless true > logs/streamlit.log 2>&1 &
    ST_PID=$!
    echo "   -> Streamlit PID: $ST_PID"
fi

sleep 3

echo ""
echo "======================================================================"
echo "👑 UNIFIED ENTERPRISE ENTRYPOINT (SINGLE PANE OF GLASS):"
echo "   👉 http://localhost:8001"
echo ""
echo "   (Everything is unified here: React 19 Sovereign UI + Live Native Engines"
echo "    + REST APIs at /api/* + Interactive Swagger Docs at /docs)"
echo ""
echo "🛠️ Internal Engineering Sidecars:"
echo "   • React Dev Server (HMR):        http://localhost:5173"
if [ "$1" == "--with-streamlit" ]; then
    echo "   • Python Streamlit Lab:          http://localhost:8502"
else
    echo "   • Streamlit:                     Disabled (run with --with-streamlit to enable)"
fi
echo "======================================================================"

