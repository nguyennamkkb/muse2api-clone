@echo off
rem Install muse2api MCP server into Claude Desktop (global) on Windows.
setlocal
cd /d "%~dp0\.."

set "PROJECT=%CD%"
set "PY=%PROJECT%\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo No .venv. Run run.bat first.
  pause
  exit /b 1
)

set "API_KEY="
if exist data\api_key ( set /p API_KEY=<data\api_key )

set "CFG=%APPDATA%\Claude\claude_desktop_config.json"
if not exist "%APPDATA%\Claude" mkdir "%APPDATA%\Claude"

python - "%CFG%" "%PY%" "%PROJECT%" "%API_KEY%" <<'PYEOF'
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
        "PYTHONPATH": proj + "\\src",
        "MUSE_BASE_URL": "http://127.0.0.1:18610",
        "MUSE_API_KEY": key,
    },
}
os.makedirs(os.path.dirname(path), exist_ok=True)
json.dump(cfg, open(path, "w"), indent=2)
print("Updated", path)
PYEOF

echo Done. Restart Claude Desktop to load the MCP server.
pause