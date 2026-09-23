@echo off
REM One-shot runner: creates the venv + installs deps on first run, then launches the app.
REM Usage: double-click, or in a terminal:  .\run.bat

setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [setup] Creating virtual environment...
    py -m venv .venv || python -m venv .venv
    echo [setup] Installing dependencies...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

echo [run] Starting server at http://localhost:8000  (Ctrl+C to stop)
".venv\Scripts\python.exe" -m uvicorn app:app --reload
