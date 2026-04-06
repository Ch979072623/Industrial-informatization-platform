# Docker 安装指南（Windows）

本指南介绍如何在 Windows 上安装 Docker Desktop，用于运行 Redis 服务。

## 方法一：Docker Desktop（推荐）

### 步骤1：检查系统要求

安装前请确认：
- Windows 10 64位 版本1903或更高（Build 18362+）
- 或 Windows 11 64位
- BIOS 中已启用虚拟化（VT-x/AMD-V）

**检查虚拟化是否启用：**
```powershell
# 打开 PowerShell，运行：
systeminfo | findstr /i "Hyper-V 要求"

# 如果显示"虚拟机监视器模式扩展：是"，则可以安装
```

### 步骤2：下载 Docker Desktop

1. 访问官网下载页面：
   https://www.docker.com/products/docker-desktop/

2. 点击 **"Download for Windows - AMD64"**

3. 下载文件：`Docker Desktop Installer.exe`（约 500MB）

### 步骤3：安装 Docker Desktop

1. **双击**下载的安装程序

2. 安装向导中：
   - ✅ 勾选 **"Use WSL 2 instead of Hyper-V"**（推荐）
   - ✅ 勾选 **"Add shortcut to desktop"**
   - 点击 **"OK"**

3. 等待安装完成（约 2-5 分钟）

4. 安装完成后，点击 **"Close and restart"**

5. **重启电脑**（必须）

### 步骤4：首次启动配置

1. 重启后，Docker Desktop 会自动启动
   - 或在开始菜单搜索 "Docker Desktop" 手动启动

2. 接受服务协议（点击 **"Accept"**）

3. 选择使用场景：
   - 选择 **"Use recommended settings"**（推荐设置）
   - 点击 **"Finish"**

4. 等待 Docker 启动（状态栏显示 "Docker Desktop starting..."）

5. 当看到 **"Docker Desktop is running"** 表示成功

### 步骤5：配置国内镜像加速（重要）

由于网络原因，国内访问 Docker Hub 很慢，需要配置镜像：

1. 打开 Docker Desktop
2. 点击右上角 **⚙️ Settings（设置）**
3. 左侧选择 **"Docker Engine"**
4. 在右侧 JSON 配置中添加 `registry-mirrors`：

```json
{
  "builder": {
    "gc": {
      "defaultKeepStorage": "20GB",
      "enabled": true
    }
  },
  "experimental": false,
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com"
  ]
}
```

5. 点击 **"Apply & Restart"**（应用并重启）

### 步骤6：验证安装

打开 PowerShell，运行：

```powershell
# 检查 Docker 版本
docker --version
# 应显示：Docker version 24.x.x, build xxxxx

# 检查 Docker Compose 版本
docker-compose --version
# 应显示：Docker Compose version v2.x.x

# 运行测试容器
docker run hello-world
# 应显示：Hello from Docker! 表示成功
```

## 方法二：不安装 Docker，使用本地 Redis（更简单）

如果你不想安装 Docker，可以直接在 Windows 上安装 Redis：

### 安装 Redis for Windows

1. 下载 Redis：
   - 访问：https://github.com/microsoftarchive/redis/releases
   - 下载：`Redis-x64-3.0.504.msi`（或最新版本）

2. 双击安装程序，一路点击 **"Next"** 完成安装

3. Redis 会自动作为 Windows 服务启动

4. 验证安装：
   ```powershell
   # 打开新的 PowerShell
   redis-cli ping
   # 应返回：PONG
   ```

### 或使用 Memurai（Redis 替代品）

Memurai 是 Redis 的 Windows 兼容版本：

1. 访问：https://www.memurai.com/
2. 下载免费版
3. 安装并启动
4. 默认端口：6379（与 Redis 相同）

## 启动项目 Redis

### 使用 Docker（方法一）

```powershell
# 在项目根目录
cd E:\Industrial informatization platform

# 启动 Redis
docker-compose up -d redis

# 验证
docker ps
docker exec defect-detection-redis redis-cli ping
```

### 使用本地 Redis（方法二）

如果已安装本地 Redis，直接启动服务即可：

```powershell
# 检查 Redis 是否运行
redis-cli ping

# 如果未运行，手动启动
redis-server
```

然后在 `.env` 文件中确保配置正确：
```env
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

## 常见问题

### Q1: 安装时提示 "WSL 2 installation is incomplete"

**解决：**
```powershell
# 1. 更新 WSL
wsl --update

# 2. 安装 Linux 内核包
# 访问：https://aka.ms/wsl2kernel
# 下载并安装：WSL2 Linux kernel update package for x64 machines

# 3. 设置 WSL 默认版本
wsl --set-default-version 2

# 4. 重启 Docker Desktop
```

### Q2: Docker 启动失败，提示 "Hardware assisted virtualization"

**解决：** 需要在 BIOS 中启用虚拟化
1. 重启电脑，按 `Del`/`F2`/`F10` 进入 BIOS
2. 找到 **"Intel Virtualization Technology"** 或 **"AMD-V"**
3. 设置为 **"Enabled"**
4. 保存并重启

### Q3: 镜像下载很慢或失败

**解决：** 确保已配置国内镜像加速（见步骤5）

如果仍然慢，可以单独配置：
```powershell
# 使用阿里云镜像拉取
docker pull registry.cn-hangzhou.aliyuncs.com/redis:7-alpine

# 然后 tag 为本地名称
docker tag registry.cn-hangzhou.aliyuncs.com/redis:7-alpine redis:7-alpine
```

### Q4: 不想用 Docker，有替代方案吗？

**有！** 本项目的 Redis 只是用于 Celery 任务队列，如果你暂时不需要异步任务，可以：

1. **跳过 Redis 安装**，直接运行后端（部分功能受限）
2. **使用 SQLite 替代**（已配置好，无需额外安装）

直接启动后端：
```powershell
conda activate defect-detection
cd backend
uvicorn app.main:app --reload
```

## 下一步

安装完成后，回到项目继续配置：

```powershell
# 1. 确保 Redis 在运行（Docker 或本地）
redis-cli ping  # 应返回 PONG

# 2. 启动后端
cd backend
uvicorn app.main:app --reload
```
