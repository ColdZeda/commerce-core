# 一条命令把本地开发环境拉起来：依赖 → 容器 → 迁移 → 种子数据 → 前后端。
# 用法（仓库根执行）： powershell -ExecutionPolicy Bypass -File scripts\dev-up.ps1
# 只做本地开发，不碰服务器；重复执行是安全的，已就绪的步骤会跳过。

param(
    [switch]$SkipSeed,
    [switch]$NoServers
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$python = Join-Path $backend ".venv\Scripts\python.exe"

function Write-Step($message) { Write-Host "==> $message" -ForegroundColor Cyan }
function Write-Ok($message) { Write-Host "    $message" -ForegroundColor Green }
function Fail($message) { Write-Host "!!  $message" -ForegroundColor Red; exit 1 }

# ---------- 前置条件 ----------
Write-Step "检查 Docker 与 Node"
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Fail "没找到 docker，请先装 Docker Desktop" }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Fail "没找到 npm，请先装 Node 18+" }
docker info --format "{{.ServerVersion}}" 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "Docker 没在跑，先启动 Docker Desktop" }
Write-Ok "docker / npm 都在"

# ---------- 容器 ----------
Write-Step "启动 MySQL 与 Redis"
Push-Location $root
docker compose -f deploy/docker-compose.yml --env-file .env up -d mysql redis | Out-Null
Pop-Location
Write-Ok "容器已启动（已存在的不会重建）"

# 等 MySQL 健康：迁移在它没起好之前跑会直接失败
Write-Step "等待 MySQL 就绪"
$deadline = (Get-Date).AddSeconds(90)
while ((Get-Date) -lt $deadline) {
    $status = docker inspect --format "{{.State.Health.Status}}" commerce-mysql 2>$null
    if ($status -eq "healthy") { break }
    Start-Sleep -Seconds 2
}
if ($status -ne "healthy") { Fail "MySQL 90 秒内没有 healthy，检查 docker compose logs mysql" }
Write-Ok "MySQL healthy"

# ---------- 后端依赖 ----------
if (-not (Test-Path $python)) {
    Write-Step "创建后端虚拟环境并安装依赖（首次会比较慢）"
    Push-Location $backend
    py -3.12 -m venv .venv
    & $python -m pip install --upgrade pip | Out-Null
    & $python -m pip install -r requirements-dev.txt
    Pop-Location
    Write-Ok "依赖装好了"
} else {
    Write-Ok "后端虚拟环境已存在，跳过安装（要重装就删掉 backend\.venv）"
}

# ---------- 迁移与种子 ----------
Write-Step "执行数据库迁移"
Push-Location $backend
& $python manage.py migrate --noinput | Out-Null
if ($LASTEXITCODE -ne 0) { Pop-Location; Fail "迁移失败" }
Write-Ok "迁移完成"

if (-not $SkipSeed) {
    Write-Step "写入演示数据（幂等，只补缺）"
    & $python manage.py seed_demo
    Write-Ok "商品、SKU 与券就绪"
}
Pop-Location

# ---------- 前端依赖 ----------
if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Write-Step "安装前端依赖"
    Push-Location $frontend
    npm install
    Pop-Location
    Write-Ok "依赖装好了"
} else {
    Write-Ok "前端依赖已存在，跳过安装"
}

if ($NoServers) {
    Write-Host ""
    Write-Host "只准备了环境，没有起服务（-NoServers）。" -ForegroundColor Yellow
    exit 0
}

# ---------- 起服务 ----------
Write-Step "启动后端 :8000 与前端 :5173"
$api = Start-Process -FilePath $python -ArgumentList "manage.py", "runserver", "127.0.0.1:8000" `
    -WorkingDirectory $backend -PassThru -WindowStyle Hidden
# Vite 只监听 localhost，避免开发机把端口暴露到局域网
$web = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "npm run dev -- --host 127.0.0.1" `
    -WorkingDirectory $frontend -PassThru -WindowStyle Hidden

# 等到两边都能连上再打印地址，免得用户点了个还没起来的链接
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/health" -UseBasicParsing -TimeoutSec 2 | Out-Null
        Invoke-WebRequest -Uri "http://127.0.0.1:5173/" -UseBasicParsing -TimeoutSec 2 | Out-Null
        $ready = $true
        break
    } catch { }
}
if (-not $ready) {
    Stop-Process -Id $api.Id, $web.Id -Force -ErrorAction SilentlyContinue
    Fail "服务没能在 30 秒内起来，看看上面 python / vite 的输出"
}

Write-Host ""
Write-Host "  站点   http://127.0.0.1:5173" -ForegroundColor Green
Write-Host "  接口   http://127.0.0.1:8000/api/v1/health" -ForegroundColor Green
Write-Host "  看板   http://127.0.0.1:5173/audit" -ForegroundColor Green
Write-Host ""
Write-Host "按 Ctrl+C 停止。" -ForegroundColor Yellow

try {
    while ($true) { Start-Sleep -Seconds 1 }
} finally {
    Write-Host "`n停止服务…" -ForegroundColor Yellow
    # cmd.exe 起的 vite 会带一串子进程，用 taskkill 整棵树收掉
    Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue
    taskkill /PID $web.Id /T /F 2>$null | Out-Null
}
