@echo off
rem Khoi chay muse2api tren Windows. Lan dau se tu tao moi truong va cai thu vien.
setlocal
cd /d "%~dp0"

where python >nul 2>nul || (echo Khong tim thay python. Cai Python 3.10+ va tick "Add to PATH". & pause & exit /b 1)
python -c "import sys; sys.exit(sys.version_info < (3, 10))" || (echo Can Python 3.10 tro len. & pause & exit /b 1)

if not exist .venv\Scripts\python.exe (
  echo ^>^> Tao moi truong ao .venv
  python -m venv .venv
)
.venv\Scripts\python -c "import muse2api" 2>nul || (
  echo ^>^> Cai thu vien ^(chi lan dau^)
  .venv\Scripts\python -m pip install -q --upgrade pip
  .venv\Scripts\python -m pip install -q -e .
)

if not exist .env (
  copy .env.example .env >nul
  echo ^>^> Da tao .env tu .env.example ^(driver=mock^).
)

rem Tu tim Chrome neu .env chua chi dinh MUSE2API_CHROMIUM_PATH
if not defined MUSE2API_CHROMIUM_PATH (
  if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "MUSE2API_CHROMIUM_PATH=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
  if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "MUSE2API_CHROMIUM_PATH=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
  if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "MUSE2API_CHROMIUM_PATH=%LocalAppData%\Google\Chrome\Application\chrome.exe"
)

.venv\Scripts\python -m muse2api
pause
