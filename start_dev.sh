#!/bin/bash
# 工业缺陷检测平台 - 开发环境启动脚本
# Bash 版本 (Linux/macOS)

set -e

SERVICE=${1:-all}

# 颜色定义
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${CYAN}"
    echo "========================================"
    echo "  $1"
    echo "========================================"
    echo -e "${NC}"
}

start_redis() {
    print_header "启动 Redis"
    docker-compose up -d redis
    echo -e "${GREEN}Redis 已启动 (端口: 6379)${NC}"
}

start_backend() {
    print_header "启动后端服务"
    
    # 检查虚拟环境
    if [ ! -d "backend/venv" ]; then
        echo -e "${YELLOW}创建虚拟环境...${NC}"
        python3 -m venv backend/venv
    fi
    
    # 激活虚拟环境
    echo -e "${YELLOW}激活虚拟环境...${NC}"
    source backend/venv/bin/activate
    
    echo -e "${YELLOW}检查依赖...${NC}"
    pip install -q -r backend/requirements.txt
    
    # 启动后端
    echo -e "${GREEN}启动 FastAPI 服务...${NC}"
    cd backend
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
    cd ..
    
    echo -e "${GREEN}后端服务已启动 (http://localhost:8000)${NC}"
    echo -e "${GREEN}API 文档: http://localhost:8000/docs${NC}"
}

start_frontend() {
    print_header "启动前端服务"
    
    cd frontend
    
    # 安装依赖
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}安装前端依赖...${NC}"
        if command -v pnpm &> /dev/null; then
            pnpm install
        else
            npm install
        fi
    fi
    
    # 启动前端
    echo -e "${GREEN}启动 Vite 开发服务器...${NC}"
    if command -v pnpm &> /dev/null; then
        pnpm dev &
    else
        npm run dev &
    fi
    
    cd ..
    
    echo -e "${GREEN}前端服务已启动 (http://localhost:5173)${NC}"
}

# 主逻辑
echo -e "${CYAN}"
echo "工业缺陷检测平台 - 开发环境启动脚本"
echo -e "${NC}"

case $SERVICE in
    redis)
        start_redis
        ;;
    backend)
        start_backend
        ;;
    frontend)
        start_frontend
        ;;
    all)
        start_redis
        start_backend
        start_frontend
        
        print_header "所有服务已启动"
        echo -e "${GREEN}前端: http://localhost:5173${NC}"
        echo -e "${GREEN}后端: http://localhost:8000${NC}"
        echo -e "${GREEN}API 文档: http://localhost:8000/docs${NC}"
        echo -e "${GREEN}Redis: localhost:6379${NC}"
        ;;
    *)
        echo "用法: $0 {all|backend|frontend|redis}"
        exit 1
        ;;
esac

echo ""
echo -e "${YELLOW}提示: 使用 'pkill -f uvicorn' 和 'pkill -f vite' 关闭服务${NC}"
echo ""
