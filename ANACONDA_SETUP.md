# Anaconda 环境配置指南

本指南介绍如何使用 Anaconda/Miniconda 配置工业缺陷检测平台的开发环境。

## 前置要求

- 已安装 [Anaconda](https://www.anaconda.com/download) 或 [Miniconda](https://docs.conda.io/en/latest/miniconda.html)
- Git（用于克隆项目）
- Node.js 18+（前端开发）
- Docker Desktop（用于 Redis）

## 1. 克隆项目

```bash
git clone <your-repo-url>
cd defect-detection-platform
```

## 2. 创建 Conda 环境

### 2.1 创建 Python 3.11 环境

```bash
# 创建新环境（推荐 Python 3.11）
conda create -n defect-detection python=3.11 -y

# 激活环境
conda activate defect-detection
```

### 2.2 验证环境

```bash
# 检查 Python 版本
python --version  # 应显示 Python 3.11.x

# 检查是否在正确的环境中
conda info --envs
```

## 3. 安装后端依赖

### 3.1 使用 pip 安装

```bash
# 确保在 defect-detection 环境中
conda activate defect-detection

# 进入后端目录
cd backend

# 安装依赖
pip install -r requirements.txt
```

### 3.2 或使用 Conda 安装主要依赖（可选）

```bash
# 安装 PyTorch（带 CUDA 支持，如果需要）
# 有 NVIDIA GPU:
conda install pytorch torchvision torchaudio pytorch-cuda=12.1 -c pytorch -c nvidia

# 仅 CPU:
conda install pytorch torchvision torchaudio cpuonly -c pytorch

# 安装其他主要依赖
conda install -c conda-forge fastapi uvicorn sqlalchemy alembic redis-py celery

# 剩余依赖使用 pip
pip install python-jose passlib python-multipart pydantic-settings aiosqlite
```

## 4. 安装前端依赖

```bash
# 进入前端目录
cd frontend

# 使用 pnpm（推荐）
npm install -g pnpm
pnpm install

# 或使用 npm
npm install

# 或使用 yarn
yarn install
```

## 5. 配置环境变量

```bash
# 在项目根目录
cp .env.example .env

# 编辑 .env 文件，根据你的环境修改配置
```

### 常用配置项

```env
# 数据库 - 使用 SQLite（开发环境）
DATABASE_URL=sqlite+aiosqlite:///./app.db

# Redis - 确保 Docker Redis 运行在 6379 端口
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# JWT 密钥 - 生产环境请修改为强密码
SECRET_KEY=your-super-secret-key-change-this-in-production
```

## 6. 启动基础设施

### 6.1 使用 Docker 启动 Redis

```bash
# 在项目根目录
docker-compose up -d redis

# 验证 Redis 是否运行
docker ps
```

### 6.2 或使用本地 Redis

如果已安装 Redis，可以直接启动：

```bash
# Windows
redis-server.exe

# Linux/macOS
redis-server
```

## 7. 初始化数据库

```bash
# 确保在 backend 目录且 conda 环境已激活
cd backend
conda activate defect-detection

# 方式1：使用 Alembic 迁移（推荐用于生产环境）
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head

# 方式2：自动创建表（开发环境）
# 数据库表会在首次启动时自动创建
```

## 8. 启动服务

### 8.1 启动后端服务

```bash
# 在 backend 目录
conda activate defect-detection

# 方式1：使用 uvicorn（推荐开发）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 方式2：使用 Python 模块
python -m app.main

# 方式3：使用启动脚本（Windows）
.\start_dev.ps1 -Service backend
```

### 8.2 启动前端服务

```bash
# 在 frontend 目录

# 使用 pnpm
pnpm dev

# 或使用 npm
npm run dev
```

### 8.3 启动 Celery Worker（可选）

```bash
# 在 backend 目录，新开一个终端
conda activate defect-detection

celery -A celery_worker worker --loglevel=info
```

## 9. 验证安装

### 9.1 后端验证

```bash
# 健康检查
curl http://localhost:8000/health

# 应返回：
# {"status":"healthy","version":"1.0.0"}
```

### 9.2 API 文档

浏览器访问：http://localhost:8000/docs

### 9.3 前端访问

浏览器访问：http://localhost:5173

## 10. 开发工作流

### 每日开发步骤

```bash
# 1. 启动 Redis（如果未运行）
docker-compose up -d redis

# 2. 激活 conda 环境
conda activate defect-detection

# 3. 启动后端（终端1）
cd backend
uvicorn app.main:app --reload

# 4. 启动前端（终端2）
cd frontend
pnpm dev
```

### 安装新依赖

```bash
# Python 依赖
conda activate defect-detection
pip install <package-name>

# 添加到 requirements.txt
pip freeze > requirements.txt

# Node.js 依赖
cd frontend
pnpm add <package-name>
```

## 11. 环境管理

### 导出环境

```bash
# 导出 conda 环境（包含所有包）
conda env export > environment.yml

# 导出精简版本（仅显式安装的包）
conda env export --from-history > environment.yml

# 导出 pip 依赖
pip freeze > requirements.txt
```

### 从文件创建环境

```bash
# 从 environment.yml 创建
conda env create -f environment.yml

# 从 requirements.txt 创建
conda create -n defect-detection python=3.11
conda activate defect-detection
pip install -r requirements.txt
```

### 删除环境

```bash
# 如果需要重新开始
conda deactivate
conda remove -n defect-detection --all
```

## 12. 常见问题

### Q1: pip 安装速度慢

```bash
# 使用清华镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 或配置全局镜像
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q2: Conda 安装 PyTorch 速度慢

```bash
# 使用清华镜像
conda install pytorch torchvision torchaudio pytorch-cuda=12.1 -c pytorch -c nvidia --override-channels -c https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/pytorch/
```

### Q3: 端口冲突

```bash
# 查看端口占用（Windows）
netstat -ano | findstr :8000

# 查看端口占用（Linux/macOS）
lsof -i :8000

# 更换端口启动
uvicorn app.main:app --reload --port 8080
```

### Q4: CUDA 版本不匹配

```bash
# 查看 CUDA 版本
nvidia-smi

# 安装对应版本的 PyTorch
# 访问 https://pytorch.org/get-started/locally/ 获取正确的安装命令
```

## 13. 生产环境部署

生产环境建议使用：
- **Python**: 3.11
- **数据库**: PostgreSQL（替换 SQLite）
- **缓存**: Redis Cluster
- **Web 服务器**: Gunicorn + Nginx
- **容器**: Docker + Kubernetes

```bash
# 安装生产级服务器
pip install gunicorn

# 使用 Gunicorn 启动
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app
```

## 14. 有用的命令

```bash
# 查看 conda 环境列表
conda env list

# 查看当前环境的包
conda list

# 更新所有包
conda update --all

# 清理缓存
conda clean --all

# 查看 Python 路径
which python  # Linux/macOS
where python  # Windows
```

## 15. 推荐的 VS Code 扩展

- Python
- Pylance
- ESLint
- Prettier
- Tailwind CSS IntelliSense
- Thunder Client（API 测试）

---

有问题请参考 [README.md](./README.md) 或提交 Issue。
