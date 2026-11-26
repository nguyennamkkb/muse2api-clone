@echo off
rem Install muse2api MCP for every supported agent CLI found on this machine.
cd /d "%~dp0\.."
python scripts\install_mcp.py
pause
