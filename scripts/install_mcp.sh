#!/usr/bin/env bash
# Install muse2api MCP for every supported agent CLI found on this machine.
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 scripts/install_mcp.py
