# 工业缺陷检测平台

基于深度学习的工业缺陷检测全流程平台，支持数据集管理、模型构建、训练、剪枝、蒸馏和实时检测。

## 技术栈

### 后端
- **FastAPI** - 高性能异步 Web 框架
- **SQLAlchemy 2.0** - 异步 ORM
- **Alembic** - 数据库迁移
- **Celery + Redis** - 异步任务队列
- **PyTorch** - 深度学习框架

### 前端
- **React 18** + **TypeScript**
- **Vite** - 构建工具
- **TailwindCSS** - CSS 框架
- **shadcn/ui** - UI 组件库
- **Zustand** - 状态管理

### 基础设施
- **SQLite** - 开发环境数据库（可切换至 PostgreSQL）
- **Redis** - 缓存和任务队列
- **Docker Compose** - 容器编排

## 项目结构

```
defect-detection-platform/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/            # API 路由
│   │   ├── core/              # 核心配置（安全、配置、事件）
│   │   ├── db/                # 数据库（模型、会话、迁移）
│   │   ├── models/            # SQLAlchemy ORM 模型
│   │   ├── schemas/           # Pydantic 数据验证
│   │   ├── services/          # 业务逻辑层
│   │   ├── tasks/             # Celery 异步任务
│   │   └── ml/                # 机器学习模块
│   ├── alembic.ini            # Alembic 配置
│   ├── celery_worker.py       # Celery Worker 入口
│   └── requirements.txt       # Python 依赖
├── frontend/                   # React 前端
│   ├── src/
│   │   ├── components/        # React 组件
│   │   ├── pages/             # 页面组件
│   │   ├── services/          # API 服务
│   │   ├── stores/            # Zustand 状态管理
│   │   ├── types/             # TypeScript 类型
│   │   └── utils/             # 工具函数
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml         # Docker 编排配置
└── .env.example               # 环境变量示例
```

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/Ch979072623/Industrial-informatization-platform.git
```

### 2. 配置环境变量

```bash
# 复制环境变量示例文件
cp .env.example .env

# 编辑 .env 文件，根据需要修改配置
```

### 3. 启动基础设施

```bash
# 启动 Redis（必需）
docker-compose up -d redis

# 如需使用 PostgreSQL，取消 docker-compose.yml 中的注释并启动
# docker-compose up -d postgres
```

### 4. 启动后端

```bash
cd backend

# 创建虚拟环境（推荐）
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动开发服务器
uvicorn app.main:app --reload

# 或使用 Python 直接运行
python -m app.main
```

后端服务将在 http://localhost:8000 启动

- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

### 5. 启动前端

```bash
cd frontend

# 安装依赖（使用 pnpm）
pnpm install

# 或使用 npm/yarn
npm install

# 启动开发服务器
pnpm dev
```

前端服务将在 http://localhost:5173 启动

### 6. 启动 Celery Worker（可选）

```bash
cd backend

# 确保 Redis 已启动
celery -A celery_worker worker --loglevel=info

# celery -A celery_worker worker --pool=solo --loglevel=info
```

## 数据库迁移

```bash
cd backend

# 创建迁移脚本
alembic revision --autogenerate -m "迁移说明"

# 执行迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1
```

## 默认账号

首次启动后，需要创建管理员账号：

```bash
# 调用注册接口创建管理员
# 或使用 API 文档界面操作
```

## API 认证

平台使用 JWT Token 进行认证：

1. 调用 `/api/v1/auth/login` 获取 access_token 和 refresh_token
2. 在请求头中携带 `Authorization: Bearer <access_token>`
3. 使用 `/api/v1/auth/refresh` 刷新 access_token

## 开发指南

### 添加新的 API 路由

1. 在 `backend/app/api/v1/` 创建新的路由文件
2. 在 `backend/app/api/v1/__init__.py` 中注册路由
3. 在 `frontend/src/services/api.ts` 中添加对应的 API 调用

### 添加新的数据库模型

1. 在 `backend/app/models/` 创建模型文件
2. 在 `backend/app/models/__init__.py` 中导入模型
3. 创建 Alembic 迁移脚本
4. 在 `backend/app/schemas/` 创建对应的 Pydantic Schema

### 添加新的 Celery 任务

1. 在 `backend/app/tasks/` 创建任务文件
2. 在 `backend/celery_worker.py` 的 include 列表中添加任务模块

## 生产部署

### 环境要求

- Python 3.11+
- Node.js 18+
- Redis 7+
- PostgreSQL 15+（推荐）
- CUDA 支持（用于 GPU 训练）

### 部署步骤

1. 设置生产环境变量
2. 使用 PostgreSQL 替换 SQLite
3. 配置 Nginx 反向代理
4. 使用 Gunicorn 运行后端
5. 构建前端静态文件

### Docker 部署

```bash
# 构建并启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## 许可证

None

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

如有问题，请通过以下方式联系：
- 邮箱: 979072623@qq.com
- 项目 Issues: https://github.com/Ch979072623/Industrial-informatization-platform/issues
