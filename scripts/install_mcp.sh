#!/usr/bin/env bash
# Install muse2api MCP server into OpenCode + Claude Desktop (global).
# Usage: bash scripts/install_mcp.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PROJECT="$(pwd)"
PY="$PROJECT/.venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "No .venv. Run ./run.sh first." >&2
  exit 1
fi
API_KEY=""
if [ -f data/api_key ]; then API_KEY=$(cat data/api_key); fi

# OpenCode config
OC="$HOME/.config/opencode/opencode.json"
python3 - "$OC" "$PY" "$PROJECT" "$API_KEY" <<'PY'
import json, sys, os
path, py, proj, key = sys.argv[1:5]
try:
    cfg = json.load(open(path))
except FileNotFoundError:
    cfg = {"$schema": "https://opencode.ai/config.json", "mcp": {}}
cfg.setdefault("mcp", {})
cfg["mcp"]["muse2api"] = {
    "type": "local",
    "command": [py, "-m", "muse2api.mcp_server"],
    "environment": {
        "PYTHONPATH": proj + "/src",
        "MUSE_BASE_URL": "http://127.0.0.1:18610",
        "MUSE_API_KEY": key,
    },
    "enabled": True,
}
os.makedirs(os.path.dirname(path), exist_ok=True)
json.dump(cfg, open(path, "w"), indent=2)
print("Updated", path)
PY

# Claude Desktop config
CD="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
python3 - "$CD" "$PY" "$PROJECT" "$API_KEY" <<'PY'
import json, sys, os
path, py, proj, key = sys.argv[1:5]
try:
    cfg = json.load(open(path))
except FileNotFoundError:
    cfg = {"mcpServers": {}}
cfg.setdefault("mcpServers", {})
cfg["mcpServers"]["muse2api"] = {
    "command": py,
    "args": ["-m", "muse2api.mcp_server"],
    "env": {
        "PYTHONPATH": proj + "/src",
        "MUSE_BASE_URL": "http://127.0.0.1:18610",
        "MUSE_API_KEY": key,
    },
}
os.makedirs(os.path.dirname(path), exist_ok=True)
json.dump(cfg, open(path, "w"), indent=2)
print("Updated", path)
PY

echo "Done. Restart OpenCode and Claude Desktop to load the MCP server."