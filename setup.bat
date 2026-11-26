@echo off
rem All-in-one installer: service + MCP for all supported agent CLIs. Windows.
setlocal
cd /d "%~dp0"

echo ^>^> Setting up Python environment
start "muse2api" cmd /c run.bat
timeout /t 5 /nobreak >nul
call scripts\install_mcp.bat

echo.
echo ^>^> Service started in a separate window.
echo ^>^> MCP configs updated for installed agents. Restart or reload them to load.
echo ^>^> Service URL: http://127.0.0.1:18610
pause