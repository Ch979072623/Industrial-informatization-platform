#!/usr/bin/env pwsh
# Anaconda 环境一键配置脚本 (Windows PowerShell)

param(
    [switch]$SkipRedis,
    [switch]$SkipFrontend,
    [string]$EnvName = "defect-detection"
)

$ErrorActionPreference = "Stop"

function Write-Header($message) {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "  $message" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan
}

function Write-Success($message) {
    Write-Host "✓ $message" -ForegroundColor Green
}

function Write-Warning($message) {
    Write-Host "⚠ $message" -ForegroundColor Yellow
}

function Write-Error($message) {
    Write-Host "✗ $message" -ForegroundColor Red
}

# 检查 Conda
Write-Header "检查 Conda 安装"
try {
    $condaVersion = conda --version
    Write-Success "Conda 已安装: $condaVersion"
} catch {
    Write-Error "未找到 Conda，请先安装 Anaconda 或 Miniconda"
    Write-Host "下载地址: https://www.anaconda.com/download"
    exit 1
}

# 检查是否在正确的目录
if (-not (Test-Path "backend/requirements.txt")) {
    Write-Error "请在项目根目录运行此脚本"
    exit 1
}

# 创建 Conda 环境
Write-Header "创建 Conda 环境: $EnvName"
$envExists = conda env list | Select-String "^$EnvName\s"
if ($envExists) {
    Write-Warning "环境 '$EnvName' 已存在"
    $recreate = Read-Host "是否删除并重新创建? (y/N)"
    if ($recreate -eq 'y' -or $recreate -eq 'Y') {
        Write-Host "删除旧环境..." -ForegroundColor Yellow
        conda deactivate 2>$null
        conda env remove -n $EnvName -y
        Write-Success "旧环境已删除"
    } else {
        Write-Warning "使用现有环境"
    }
}

if (-not $envExists -or $recreate -eq 'y' -or $recreate -eq 'Y') {
    Write-Host "创建新环境 (Python 3.11)..." -ForegroundColor Yellow
    conda create -n $EnvName python=3.11 -y
    Write-Success "环境创建成功"
}

# 激活环境并安装依赖
Write-Header "安装 Python 依赖"
Write-Host "激活环境..." -ForegroundColor Yellow
conda activate $EnvName

Write-Host "升级 pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

Write-Host "安装后端依赖..." -ForegroundColor Yellow
Set-Location backend
pip install -r requirements.txt
Set-Location ..
Write-Success "Python 依赖安装完成"

# 创建 .env 文件
Write-Header "配置环境变量"
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Success "已创建 .env 文件，请根据需要修改配置"
} else {
    Write-Warning ".env 文件已存在，跳过创建"
}

# 启动 Redis
if (-not $SkipRedis) {
    Write-Header "启动 Redis (Docker)"
    $dockerExists = Get-Command docker -ErrorAction SilentlyContinue
    if ($dockerExists) {
        try {
            docker-compose up -d redis
            Write-Success "Redis 已启动"
            
            # 等待 Redis 就绪
            Write-Host "等待 Redis 就绪..." -ForegroundColor Yellow
            Start-Sleep -Seconds 3
            
            # 测试连接
            $redisTest = docker exec defect-detection-redis redis-cli ping 2>$null
            if ($redisTest -eq "PONG") {
                Write-Success "Redis 连接正常"
            } else {
                Write-Warning "Redis 可能未完全启动，稍后可手动检查"
            }
        } catch {
            Write-Warning "Docker 启动失败，请手动启动 Redis"
        }
    } else {
        Write-Warning "未找到 Docker，请手动安装并启动 Redis"
        Write-Host "Redis 下载地址: https://redis.io/download"
    }
}

# 安装前端依赖
if (-not $SkipFrontend) {
    Write-Header "安装前端依赖"
    $nodeExists = Get-Command node -ErrorAction SilentlyContinue
    if ($nodeExists) {
        Set-Location frontend
        
        # 检查 pnpm
        $pnpmExists = Get-Command pnpm -ErrorAction SilentlyContinue
        if ($pnpmExists) {
            Write-Host "使用 pnpm 安装依赖..." -ForegroundColor Yellow
            pnpm install
        } else {
            Write-Host "使用 npm 安装依赖..." -ForegroundColor Yellow
            npm install
        }
        
        Set-Location ..
        Write-Success "前端依赖安装完成"
    } else {
        Write-Warning "未找到 Node.js，跳过前端依赖安装"
        Write-Host "Node.js 下载地址: https://nodejs.org/"
    }
}

# 初始化数据库
Write-Header "初始化数据库"
Set-Location backend
conda activate $EnvName

# 检查 Alembic
if (-not (Test-Path "alembic.ini")) {
    Write-Warning "未找到 Alembic 配置，跳过数据库迁移"
} else {
    Write-Host "创建初始数据库迁移..." -ForegroundColor Yellow
    try {
        alembic revision --autogenerate -m "Initial migration"
        alembic upgrade head
        Write-Success "数据库初始化完成"
    } catch {
        Write-Warning "数据库迁移失败，将在首次启动时自动创建表"
    }
}
Set-Location ..

# 完成
Write-Header "环境配置完成! 🎉"
Write-Host ""
Write-Host "启动命令:" -ForegroundColor Cyan
Write-Host "  1. 激活环境:     conda activate $EnvName" -ForegroundColor White
Write-Host "  2. 启动后端:     cd backend && uvicorn app.main:app --reload" -ForegroundColor White
Write-Host "  3. 启动前端:     cd frontend && pnpm dev" -ForegroundColor White
Write-Host ""
Write-Host "访问地址:" -ForegroundColor Cyan
Write-Host "  - 前端: http://localhost:5173" -ForegroundColor White
Write-Host "  - 后端: http://localhost:8000" -ForegroundColor White
Write-Host "  - API 文档: http://localhost:8000/docs" -ForegroundColor White
Write-Host ""

# 创建启动快捷方式
$startScript = @"
@echo off
echo Starting Defect Detection Platform...

start "Redis" cmd /c "docker-compose up -d redis"
start "Backend" cmd /k "conda activate $EnvName && cd backend && uvicorn app.main:app --reload"
start "Frontend" cmd /k "cd frontend && pnpm dev"

echo Services starting...
echo Frontend: http://localhost:5173
echo Backend: http://localhost:8000
pause
"@

$startScript | Out-File -FilePath "start_all.bat" -Encoding UTF8
Write-Success "已创建 start_all.bat 快速启动脚本"
