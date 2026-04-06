#!/bin/bash
# Anaconda 环境一键配置脚本 (Linux/macOS)

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 默认配置
ENV_NAME="defect-detection"
SKIP_REDIS=false
SKIP_FRONTEND=false

# 解析参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-redis)
            SKIP_REDIS=true
            shift
            ;;
        --skip-frontend)
            SKIP_FRONTEND=true
            shift
            ;;
        --env-name)
            ENV_NAME="$2"
            shift 2
            ;;
        *)
            echo "未知参数: $1"
            exit 1
            ;;
    esac
done

print_header() {
    echo -e "${CYAN}"
    echo "========================================"
    echo "  $1"
    echo "========================================"
    echo -e "${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# 检查 Conda
print_header "检查 Conda 安装"
if command -v conda &> /dev/null; then
    CONDA_VERSION=$(conda --version)
    print_success "Conda 已安装: $CONDA_VERSION"
else
    print_error "未找到 Conda，请先安装 Anaconda 或 Miniconda"
    echo "下载地址: https://www.anaconda.com/download"
    exit 1
fi

# 检查是否在正确的目录
if [ ! -f "backend/requirements.txt" ]; then
    print_error "请在项目根目录运行此脚本"
    exit 1
fi

# 创建 Conda 环境
print_header "创建 Conda 环境: $ENV_NAME"
if conda env list | grep -q "^$ENV_NAME "; then
    print_warning "环境 '$ENV_NAME' 已存在"
    read -p "是否删除并重新创建? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "删除旧环境..."
        conda deactivate 2>/dev/null || true
        conda env remove -n $ENV_NAME -y
        print_success "旧环境已删除"
        RECREATE=true
    else
        print_warning "使用现有环境"
        RECREATE=false
    fi
else
    RECREATE=true
fi

if [ "$RECREATE" = true ]; then
    echo "创建新环境 (Python 3.11)..."
    conda create -n $ENV_NAME python=3.11 -y
    print_success "环境创建成功"
fi

# 激活环境并安装依赖
print_header "安装 Python 依赖"
echo "激活环境..."
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate $ENV_NAME

echo "升级 pip..."
pip install --upgrade pip

echo "安装后端依赖..."
cd backend
pip install -r requirements.txt
cd ..
print_success "Python 依赖安装完成"

# 创建 .env 文件
print_header "配置环境变量"
if [ ! -f ".env" ]; then
    cp .env.example .env
    print_success "已创建 .env 文件，请根据需要修改配置"
else
    print_warning ".env 文件已存在，跳过创建"
fi

# 启动 Redis
if [ "$SKIP_REDIS" = false ]; then
    print_header "启动 Redis (Docker)"
    if command -v docker &> /dev/null; then
        if docker-compose up -d redis; then
            print_success "Redis 已启动"
            
            # 等待 Redis 就绪
            echo "等待 Redis 就绪..."
            sleep 3
            
            # 测试连接
            if docker exec defect-detection-redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
                print_success "Redis 连接正常"
            else
                print_warning "Redis 可能未完全启动，稍后可手动检查"
            fi
        else
            print_warning "Docker 启动失败，请手动启动 Redis"
        fi
    else
        print_warning "未找到 Docker，请手动安装并启动 Redis"
        echo "Redis 下载地址: https://redis.io/download"
    fi
fi

# 安装前端依赖
if [ "$SKIP_FRONTEND" = false ]; then
    print_header "安装前端依赖"
    if command -v node &> /dev/null; then
        cd frontend
        
        # 检查 pnpm
        if command -v pnpm &> /dev/null; then
            echo "使用 pnpm 安装依赖..."
            pnpm install
        else
            echo "使用 npm 安装依赖..."
            npm install
        fi
        
        cd ..
        print_success "前端依赖安装完成"
    else
        print_warning "未找到 Node.js，跳过前端依赖安装"
        echo "Node.js 下载地址: https://nodejs.org/"
    fi
fi

# 初始化数据库
print_header "初始化数据库"
cd backend
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate $ENV_NAME

# 检查 Alembic
if [ ! -f "alembic.ini" ]; then
    print_warning "未找到 Alembic 配置，跳过数据库迁移"
else
    echo "创建初始数据库迁移..."
    if alembic revision --autogenerate -m "Initial migration" && alembic upgrade head; then
        print_success "数据库初始化完成"
    else
        print_warning "数据库迁移失败，将在首次启动时自动创建表"
    fi
fi
cd ..

# 完成
print_header "环境配置完成! 🎉"
echo ""
echo -e "${CYAN}启动命令:${NC}"
echo -e "  ${WHITE}1. 激活环境:     conda activate $ENV_NAME${NC}"
echo -e "  ${WHITE}2. 启动后端:     cd backend && uvicorn app.main:app --reload${NC}"
echo -e "  ${WHITE}3. 启动前端:     cd frontend && pnpm dev${NC}"
echo ""
echo -e "${CYAN}访问地址:${NC}"
echo -e "  ${WHITE}- 前端: http://localhost:5173${NC}"
echo -e "  ${WHITE}- 后端: http://localhost:8000${NC}"
echo -e "  ${WHITE}- API 文档: http://localhost:8000/docs${NC}"
echo ""

# 创建启动脚本
cat > start_all.sh << EOF
#!/bin/bash
# 一键启动所有服务

echo "启动工业缺陷检测平台..."

# 启动 Redis
docker-compose up -d redis

# 启动后端（新终端）
if command -v gnome-terminal &> /dev/null; then
    gnome-terminal -- bash -c "conda activate $ENV_NAME && cd backend && uvicorn app.main:app --reload; exec bash"
elif command -v osascript &> /dev/null; then
    # macOS
    osascript -e "tell application \"Terminal\" to do script \"conda activate $ENV_NAME && cd $(pwd)/backend && uvicorn app.main:app --reload\""
else
    echo "请手动启动后端: cd backend && uvicorn app.main:app --reload"
fi

# 启动前端（新终端）
if command -v gnome-terminal &> /dev/null; then
    gnome-terminal -- bash -c "cd frontend && pnpm dev; exec bash"
elif command -v osascript &> /dev/null; then
    osascript -e "tell application \"Terminal\" to do script \"cd $(pwd)/frontend && pnpm dev\""
else
    echo "请手动启动前端: cd frontend && pnpm dev"
fi

echo "服务启动中..."
echo "前端: http://localhost:5173"
echo "后端: http://localhost:8000"
EOF

chmod +x start_all.sh
print_success "已创建 start_all.sh 快速启动脚本"
