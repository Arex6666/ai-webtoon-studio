@echo off
echo ====================================
echo AI Webtoon Studio - Dev Environment
echo ====================================
echo.

REM Check if Docker is running
docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker is not running. Please start Docker Desktop first.
    pause
    exit /b 1
)

echo Starting infrastructure services (PostgreSQL, Redis, MinIO)...
cd docker
docker compose up -d postgres redis minio
cd ..

echo.
echo Waiting for services to be ready...
timeout /t 5 /nobreak >nul

echo.
echo Starting backend API...
start cmd /k "cd apps\api && python -m venv venv 2>nul && venv\Scripts\activate && pip install -r requirements.txt && python -c \"from app.core.database import init_db; init_db()\" && uvicorn app.main:app --reload --port 8000"

echo.
echo Starting frontend...
start cmd /k "cd apps\web && npm install && npm run dev"

echo.
echo ====================================
echo Services starting...
echo.
echo Frontend: http://localhost:3000
echo Backend:  http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo MinIO:    http://localhost:9001 (minioadmin/minioadmin)
echo ====================================
echo.
pause
