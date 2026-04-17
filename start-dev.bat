@echo off
setlocal enabledelayedexpansion
title Aneriam Dev Startup

echo ============================================================
echo   Aneriam - Development Environment Startup
echo ============================================================
echo.

:: ----------------------------------------------------------------
:: Step 1 — Check Docker is running
:: ----------------------------------------------------------------
echo [1/5] Checking Docker...
docker info >nul 2>&1
if errorlevel 1 (
    echo.
    echo   Docker is not running.
    echo   Please start Docker Desktop and then run this script again.
    echo.
    pause
    exit /b 1
)
echo   Docker is running.

:: ----------------------------------------------------------------
:: Step 2 — Start the database
:: ----------------------------------------------------------------
echo.
echo [2/5] Starting the database...
cd /d "%~dp0"
docker-compose up -d >nul 2>&1
if errorlevel 1 (
    echo   ERROR: Could not start Docker database. Check docker-compose.yml.
    pause
    exit /b 1
)
echo   Database container started.

:: Wait briefly for Postgres to accept connections
echo   Waiting for Postgres to be ready...
timeout /t 4 /nobreak >nul

:: ----------------------------------------------------------------
:: Step 3 — Run database migrations
:: ----------------------------------------------------------------
echo.
echo [3/5] Running database migrations...
cd /d "%~dp0backend"

:: Check if alembic is available
alembic --version >nul 2>&1
if errorlevel 1 (
    echo   ERROR: alembic not found. Make sure your Python environment is active.
    echo   Try running:  pip install -r requirements.txt
    pause
    exit /b 1
)

alembic upgrade heads
if errorlevel 1 (
    echo.
    echo   ERROR: Migrations failed. Check the output above.
    echo   If the database has stale data, run:  docker-compose down -v
    echo   Then run this script again to start fresh.
    pause
    exit /b 1
)
echo   Migrations complete.

:: ----------------------------------------------------------------
:: Step 4 — Start the backend API  (new window)
:: ----------------------------------------------------------------
echo.
echo [4/5] Starting the backend API on http://localhost:8000 ...
start "Aneriam Backend" cmd /k "cd /d "%~dp0backend" && python -m app.main"

:: Give it a moment to start before launching frontend
timeout /t 2 /nobreak >nul

:: ----------------------------------------------------------------
:: Step 5 — Start the frontend  (new window)
:: ----------------------------------------------------------------
echo.
echo [5/5] Starting the frontend on http://localhost:5173 ...
start "Aneriam Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

:: ----------------------------------------------------------------
:: Done
:: ----------------------------------------------------------------
echo.
echo ============================================================
echo   All services starting up.
echo.
echo   Frontend  ->  http://localhost:5173
echo   Backend   ->  http://localhost:8000
echo   API docs  ->  http://localhost:8000/docs
echo.
echo   Two new windows have opened:
echo     "Aneriam Backend"  - API server (keep open)
echo     "Aneriam Frontend" - Dev server (keep open)
echo.
echo   To stop everything: close those two windows,
echo   then run  docker-compose down  in this folder.
echo ============================================================
echo.

:: Open the app in the default browser after a short delay
timeout /t 5 /nobreak >nul
start http://localhost:5173

exit /b 0
