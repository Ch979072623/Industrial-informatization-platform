# 工业缺陷检测平台 - 开发环境启动脚本
# PowerShell 版本

param(
    [Parameter()]
    [ValidateSet("all", "backend", "frontend", "redis")]
    [string]$Service = "all"
)

$ErrorActionPreference = "Stop"

function Write-Header($message) {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "  $message" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan
}

function Start-Redis() {
    Write-Header "启动 Redis"
    docker-compose up -d redis
    Write-Host "Redis 已启动 (端口: 6379)" -ForegroundColor Green
}

function Start-Backend() {
    Write-Header "启动后端服务"
    
    # 检查虚拟环境
    if (-not (Test-Path "backend/venv")) {
        Write-Host "创建虚拟环境..." -ForegroundColor Yellow
        python -m venv backend/venv
    }
    
    # 激活虚拟环境并安装依赖
    Write-Host "激活虚拟环境..." -ForegroundColor Yellow
    & backend/venv/Scripts/Activate.ps1
    
    Write-Host "检查依赖..." -ForegroundColor Yellow
    pip install -q -r backend/requirements.txt
    
    # 启动后端
    Write-Host "启动 FastAPI 服务..." -ForegroundColor Green
    Set-Location backend
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
    Set-Location ..
    
    Write-Host "后端服务已启动 (http://localhost:8000)" -ForegroundColor Green
    Write-Host "API 文档: http://localhost:8000/docs" -ForegroundColor Green
}

function Start-Frontend() {
    Write-Header "启动前端服务"
    
    # 检查 pnpm
    $pnpmExists = Get-Command pnpm -ErrorAction SilentlyContinue
    $npmExists = Get-Command npm -ErrorAction SilentlyContinue
    
    Set-Location frontend
    
    # 安装依赖
    if (-not (Test-Path "node_modules")) {
        Write-Host "安装前端依赖..." -ForegroundColor Yellow
        if ($pnpmExists) {
            pnpm install
        } elseif ($npmExists) {
            npm install
        } else {
            Write-Error "未找到 pnpm 或 npm，请先安装 Node.js"
            exit 1
        }
    }
    
    # 启动前端
    Write-Host "启动 Vite 开发服务器..." -ForegroundColor Green
    if ($pnpmExists) {
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "pnpm dev"
    } else {
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "npm run dev"
    }
    
    Set-Location ..
    
    Write-Host "前端服务已启动 (http://localhost:5173)" -ForegroundColor Green
}

# 主逻辑
Write-Host "`n工业缺陷检测平台 - 开发环境启动脚本`n" -ForegroundColor Cyan

switch ($Service) {
    "redis" {
        Start-Redis
    }
    "backend" {
        Start-Backend
    }
    "frontend" {
        Start-Frontend
    }
    "all" {
        Start-Redis
        Start-Backend
        Start-Frontend
        
        Write-Header "所有服务已启动"
        Write-Host "前端: http://localhost:5173" -ForegroundColor Green
        Write-Host "后端: http://localhost:8000" -ForegroundColor Green
        Write-Host "API 文档: http://localhost:8000/docs" -ForegroundColor Green
        Write-Host "Redis: localhost:6379" -ForegroundColor Green
    }
}

Write-Host "`n提示: 使用 Ctrl+C 关闭服务，或关闭打开的终端窗口`n" -ForegroundColor Yellow
