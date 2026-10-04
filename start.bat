@echo off
title AgenticInventory AI - Launcher
color 0A

echo ============================================================
echo         AgenticInventory AI - One-Click Launcher
echo ============================================================
echo.

cd /d "%~dp0"

:: ─── 1. Check prerequisites ─────────────────────────────
echo [1/5] Checking prerequisites...

where node >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Node.js is not installed or not in PATH.
    pause
    exit /b 1
)

if not exist "backend\.venv\Scripts\python.exe" (
    echo ERROR: Python virtual environment not found at backend\.venv
    echo Run:  cd backend ^&^& python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

echo    OK - Node.js and Python venv found.
echo.

:: ─── 2. Ensure backend/.env exists ──────────────────────
if not exist "backend\.env" (
    echo [2/5] Creating backend\.env from .env.example...
    copy ".env.example" "backend\.env" >nul
    echo    Created backend\.env - using SQLite by default.
) else (
    echo [2/5] backend\.env exists - skipping.
)
echo.

:: ─── 3. Frontend dependencies ───────────────────────────
echo [3/5] Checking frontend dependencies...
if not exist "frontend\node_modules" (
    echo    Installing npm packages...
    cd frontend
    call npm install
    cd ..
) else (
    echo    node_modules exists - skipping install.
)
echo.

:: ─── 4. Backend dependencies ────────────────────────────
echo [4/5] Checking backend dependencies...
cd backend
call .venv\Scripts\activate.bat
pip show fastapi >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo    Installing Python packages...
    pip install -r requirements.txt
) else (
    echo    Backend packages installed - skipping.
)
cd ..
echo.

:: ─── 5. Launch backend and frontend ─────────────────────
echo [5/5] Starting servers...
echo.

:: Free port 8000 if a previous uvicorn instance is still holding it
:: (common cause of "WinError 10013: access to socket forbidden")
echo    Checking port 8000...
for /f "tokens=5" %%P in ('netstat -ano -p tcp ^| findstr /R /C:":8000 .*LISTENING"') do (
    echo    Stopping orphan process %%P holding port 8000...
    taskkill /F /PID %%P >nul 2>&1
)

echo.
echo    Backend  : http://localhost:8000
echo    Frontend : http://localhost:5173
echo    API Docs : http://localhost:8000/docs
echo    Database : SQLite (backend\agenticinventory.db) - auto-created
echo.
echo    Close the server windows to stop.
echo ============================================================
echo.

:: Start backend — bind to 127.0.0.1 (avoids needing firewall permission for 0.0.0.0)
:: reload only watches app/ folder (NOT .venv to avoid reload storms)
start "AgenticInventory - Backend" cmd /k "cd /d "%~dp0backend" && call .venv\Scripts\activate.bat && python -m uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port 8000"

start "AgenticInventory - Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

timeout /t 5 /nobreak >nul
start http://localhost:5173

echo.
echo Both servers launched. Browser opening at http://localhost:5173
echo Close this window anytime - the servers will keep running.
pause >nul
