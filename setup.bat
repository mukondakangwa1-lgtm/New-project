@echo off
REM Digital Campus — One-command setup (Windows)
REM Usage:  setup.bat         (interactive)
REM         setup.bat sqlite
REM         setup.bat postgres
setlocal

echo ========================================
echo   Digital Campus — Setup (Windows)
echo ========================================

REM 1. Check Python
python --version >nul 2>&1
if errorlevel 1 (
  echo ❌ python not found — install Python 3.11+ from python.org and check "Add to PATH"
  pause
  exit /b 1
)
echo ✅ Python: 
python --version

REM 2. Backend venv + deps
echo.
echo → Installing backend deps...
cd services\backend
if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\pip install -q -r requirements.txt
echo ✅ Deps installed

REM 3. Choose DB
set MODE=%1
if "%MODE%"=="" (
  echo.
  echo Which database?
  echo   1) SQLite  (laptop, zero setup — recommended)
  echo   2) PostgreSQL (needs Postgres installed or Docker)
  set /p CHOICE="Choose [1/2]: "
  if "%CHOICE%"=="2" (set MODE=postgres) else (set MODE=sqlite)
)

if "%MODE%"=="postgres" goto PG
if "%MODE%"=="pg" goto PG
goto SQLITE

:PG
echo.
echo → Switching to PostgreSQL...
python scripts\switch_db.py postgres --apply
echo.
echo → If using Docker, start Postgres with: docker-compose up -d db redis
echo    (wait 5s then continue)
timeout /t 5 >nul
goto INIT

:SQLITE
echo.
echo → Switching to SQLite...
python scripts\switch_db.py sqlite --apply
goto INIT

:INIT
echo.
echo → Initializing database...
.venv\Scripts\python scripts\init_db.py --seed
echo.
.venv\Scripts\python scripts\db_check.py

echo.
echo ========================================
echo   ✅ Setup complete!
echo   Start server: cd services\backend ^&^& .venv\Scripts\uvicorn app.main:app --reload --port 8000
echo   Login: admin@campus.edu / superadmin123
echo   Docs: http://localhost:8000/docs  ^|  Health: http://localhost:8000/api/v1/health/db
echo ========================================
pause
