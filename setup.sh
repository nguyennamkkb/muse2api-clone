#!/usr/bin/env bash
# All-in-one installer: service + MCP for all supported agent CLIs. macOS/Linux.
set -euo pipefail
cd "$(dirname "$0")"

echo ">> Setting up Python environment"
bash run.sh &
SVC_PID=$!
# wait for venv creation / install
sleep 3
# run install (idempotent)
bash scripts/install_mcp.sh

echo ""
echo ">> Service is starting in background (PID $SVC_PID)."
echo ">> MCP configs updated for installed agents. Restart or reload them to load."
echo ">> Service URL: http://127.0.0.1:18610"
# keep service in foreground
wait $SVC_PID