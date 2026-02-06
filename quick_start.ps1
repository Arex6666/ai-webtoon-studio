# AI Webtoon Studio - 快速启动脚本
# 自动检查并启动所有必需服务

Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host "       AI Webtoon Studio - P0 MVP 快速启动" -ForegroundColor Cyan
Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host ""

# 配置变量
$COMFYUI_PATH = "D:\ComfyUI\ComfyUI"
$API_PATH = "D:\ai-webtoon-studio\apps\api"
$WEB_PATH = "D:\ai-webtoon-studio\apps\web"

# 检查 ComfyUI 是否已启动
Write-Host "1. 检查 ComfyUI..." -ForegroundColor Yellow
$comfyuiRunning = $false
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:8188/system_stats" -TimeoutSec 2 -ErrorAction SilentlyContinue
    if ($response.StatusCode -eq 200) {
        Write-Host "   ✅ ComfyUI 已运行" -ForegroundColor Green
        $comfyuiRunning = $true
    }
}
catch {
    Write-Host "   ❌ ComfyUI 未运行" -ForegroundColor Red
}

# 如果 ComfyUI 未运行，尝试启动
if (-not $comfyuiRunning) {
    if (Test-Path $COMFYUI_PATH) {
        Write-Host "   🚀 正在启动 ComfyUI..." -ForegroundColor Cyan
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$COMFYUI_PATH'; python main.py"
        Write-Host "   ⏳ 等待 ComfyUI 启动 (30秒)..." -ForegroundColor Yellow
        Start-Sleep -Seconds 30
    }
    else {
        Write-Host "   ⚠️  ComfyUI 路径不存在: $COMFYUI_PATH" -ForegroundColor Yellow
        Write-Host "   请先安装 ComfyUI 或修改脚本中的路径" -ForegroundColor Yellow
    }
}

# 检查后端 API
Write-Host ""
Write-Host "2. 检查后端 API..." -ForegroundColor Yellow
$apiRunning = $false
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/" -TimeoutSec 2 -ErrorAction SilentlyContinue
    if ($response.StatusCode -eq 200) {
        Write-Host "   ✅ 后端 API 已运行" -ForegroundColor Green
        $apiRunning = $true
    }
}
catch {
    Write-Host "   ❌ 后端 API 未运行" -ForegroundColor Red
}

# 如果后端未运行，尝试启动
if (-not $apiRunning) {
    if (Test-Path $API_PATH) {
        Write-Host "   🚀 正在启动后端 API..." -ForegroundColor Cyan
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$API_PATH'; uvicorn app.main:app --reload --port 8000"
        Write-Host "   ⏳ 等待 API 启动 (10秒)..." -ForegroundColor Yellow
        Start-Sleep -Seconds 10
    }
    else {
        Write-Host "   ⚠️  API 路径不存在: $API_PATH" -ForegroundColor Yellow
    }
}

# 检查前端
Write-Host ""
Write-Host "3. 检查前端..." -ForegroundColor Yellow
$webRunning = $false
try {
    $response = Invoke-WebRequest -Uri "http://localhost:3001/" -TimeoutSec 2 -ErrorAction SilentlyContinue
    if ($response.StatusCode -eq 200) {
        Write-Host "   ✅ 前端已运行" -ForegroundColor Green
        $webRunning = $true
    }
}
catch {
    Write-Host "   ❌ 前端未运行" -ForegroundColor Red
}

# 如果前端未运行，尝试启动
if (-not $webRunning) {
    if (Test-Path $WEB_PATH) {
        Write-Host "   🚀 正在启动前端..." -ForegroundColor Cyan
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$WEB_PATH'; npm run dev"
        Write-Host "   ⏳ 等待前端启动 (15秒)..." -ForegroundColor Yellow
        Start-Sleep -Seconds 15
    }
    else {
        Write-Host "   ⚠️  前端路径不存在: $WEB_PATH" -ForegroundColor Yellow
    }
}

# 最终验证
Write-Host ""
Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host "                        启动完成" -ForegroundColor Cyan
Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host ""

$allRunning = $true

# 重新检查所有服务
Write-Host "服务状态:" -ForegroundColor Yellow
try {
    Invoke-WebRequest -Uri "http://127.0.0.1:8188/system_stats" -TimeoutSec 2 -ErrorAction Stop | Out-Null
    Write-Host "  ✅ ComfyUI:  http://127.0.0.1:8188" -ForegroundColor Green
}
catch {
    Write-Host "  ❌ ComfyUI:  未运行" -ForegroundColor Red
    $allRunning = $false
}

try {
    Invoke-WebRequest -Uri "http://localhost:8000/" -TimeoutSec 2 -ErrorAction Stop | Out-Null
    Write-Host "  ✅ 后端API:  http://localhost:8000" -ForegroundColor Green
}
catch {
    Write-Host "  ❌ 后端API:  未运行" -ForegroundColor Red
    $allRunning = $false
}

try {
    Invoke-WebRequest -Uri "http://localhost:3001/" -TimeoutSec 2 -ErrorAction Stop | Out-Null
    Write-Host "  ✅ 前端:     http://localhost:3001" -ForegroundColor Green
}
catch {
    Write-Host "  ❌ 前端:     未运行" -ForegroundColor Red
    $allRunning = $false
}

Write-Host ""
if ($allRunning) {
    Write-Host "🎉 所有服务已启动！访问 http://localhost:3001 开始使用" -ForegroundColor Green
    Write-Host ""
    Write-Host "下一步:" -ForegroundColor Cyan
    Write-Host "  1. 创建项目" -ForegroundColor White
    Write-Host "  2. 输入剧本" -ForegroundColor White
    Write-Host "  3. AI 分镜 → 上传参考图 → 渲染 → 导出" -ForegroundColor White
    
    # 自动打开浏览器
    Start-Process "http://localhost:3001"
}
else {
    Write-Host "⚠️  部分服务未启动，请检查错误信息" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "手动启动命令:" -ForegroundColor Cyan
    Write-Host "  ComfyUI: cd $COMFYUI_PATH; python main.py" -ForegroundColor White
    Write-Host "  后端API: cd $API_PATH; uvicorn app.main:app --reload" -ForegroundColor White
    Write-Host "  前端:    cd $WEB_PATH; npm run dev" -ForegroundColor White
}

Write-Host ""
Write-Host "按任意键退出..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
