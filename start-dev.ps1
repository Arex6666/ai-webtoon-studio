# AI Webtoon Studio - Development Environment Startup Script

Write-Host "====================================" -ForegroundColor Cyan
Write-Host "AI Webtoon Studio - Dev Environment" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# Check Docker
try {
    docker info | Out-Null
} catch {
    Write-Host "[ERROR] Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Starting infrastructure services (PostgreSQL, Redis, MinIO)..." -ForegroundColor Yellow
Set-Location docker
docker compose up -d postgres redis minio
Set-Location ..

Write-Host ""
Write-Host "Waiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "Starting backend API..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location apps\api; if (-not (Test-Path venv)) { python -m venv venv }; .\venv\Scripts\Activate.ps1; pip install -r requirements.txt; python -c 'from app.core.database import init_db; init_db()'; uvicorn app.main:app --reload --port 8000"
)

Write-Host ""
Write-Host "Starting frontend..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command", 
    "Set-Location apps\web; npm install; npm run dev"
)

Write-Host ""
Write-Host "====================================" -ForegroundColor Green
Write-Host "Services starting..." -ForegroundColor Green
Write-Host ""
Write-Host "Frontend: http://localhost:3000" -ForegroundColor White
Write-Host "Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "API Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host "MinIO:    http://localhost:9001 (minioadmin/minioadmin)" -ForegroundColor White
Write-Host "====================================" -ForegroundColor Green
Write-Host ""

Read-Host "Press Enter to exit"
