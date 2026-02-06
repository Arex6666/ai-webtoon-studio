# AI Webtoon Studio 开发启动脚本
# 使用方法: .\scripts\start-dev.ps1

Write-Host "🚀 启动 AI Webtoon Studio 开发环境..." -ForegroundColor Cyan

# 检查 Python 虚拟环境
$venvPath = "apps\api\venv"
if (-not (Test-Path $venvPath)) {
    Write-Host "📦 创建 Python 虚拟环境..." -ForegroundColor Yellow
    Set-Location apps\api
    python -m venv venv
    Set-Location ..\..
}

# 启动后端 API (新窗口)
Write-Host "🔌 启动后端 API..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
    Set-Location '$PWD\apps\api'
    .\venv\Scripts\Activate.ps1
    pip install -r requirements.txt 2>&1 | Out-Null
    Write-Host '✅ 后端 API 已启动: http://localhost:8000' -ForegroundColor Green
    uvicorn app.main:app --reload --port 8000
"@

# 等待后端启动
Start-Sleep -Seconds 3

# 启动 Celery Worker (新窗口)
Write-Host "⚙️ 启动 Celery Worker..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
    Set-Location '$PWD\apps\api'
    .\venv\Scripts\Activate.ps1
    Write-Host '✅ Celery Worker 已启动' -ForegroundColor Green
    celery -A app.celery_app:celery_app worker --loglevel=info --pool=solo
"@

# 启动前端 (新窗口)
Write-Host "🎨 启动前端..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", @"
    Set-Location '$PWD\apps\web'
    npm install 2>&1 | Out-Null
    Write-Host '✅ 前端已启动: http://localhost:3000' -ForegroundColor Green
    npm run dev
"@

Write-Host ""
Write-Host "✨ 所有服务已启动！" -ForegroundColor Cyan
Write-Host ""
Write-Host "  📝 后端 API:    http://localhost:8000" -ForegroundColor White
Write-Host "  📚 API 文档:    http://localhost:8000/docs" -ForegroundColor White
Write-Host "  🎨 前端:        http://localhost:3000" -ForegroundColor White
Write-Host ""
Write-Host "按任意键关闭此窗口..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
