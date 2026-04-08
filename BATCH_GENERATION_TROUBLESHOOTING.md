# 批量生成故障排查指南

## 问题描述

预览图生成成功，但批量生成任务卡在进度 0%。

---

## 常见原因

### 1. Hugging Face 首次请求超时

**现象**：任务开始但长时间没有进展

**原因**：Hugging Face 首次加载模型需要 10-20 秒，如果超过 Celery 任务超时时间会失败

**解决**：
- 使用 Replicate 代替 Hugging Face（更稳定）
- 或减少生成数量（先测试 5-10 张）

---

### 2. Celery Worker 日志查看

打开新的终端窗口，查看 Celery 日志：

```bash
cd backend
conda activate defect-detection
celery -A app.tasks.celery_app worker --loglevel=info -P solo
```

查看是否有以下错误：
- `TimeoutError` - API 调用超时
- `GenerationError` - 生成器错误
- `RateLimit` - 请求太频繁

---

### 3. 检查任务状态

在浏览器开发者工具中查看网络请求：

1. 打开 Chrome DevTools (F12)
2. 切换到 Network 标签
3. 查看 `/api/v1/generation/execute` 请求
4. 检查响应状态码

---

### 4. 后端日志查看

在启动后端的终端窗口查看实时日志：

```bash
# 应该能看到类似日志：
INFO - 初始化 Stable Diffusion API 生成器...
INFO - 配置: api_endpoint=..., prompt=...
INFO - 开始生成 10 张图像...
INFO - 生成第 1/10 张图像...
INFO - 调用 generate_single(seed=0)...
```

如果看不到这些日志，说明任务可能没有正确启动。

---

## 快速排查步骤

### 步骤 1：测试小批量

先测试生成 **1 张**图像：
1. 设置生成数量为 1
2. 点击"开始生成"
3. 观察任务列表状态

### 步骤 2：检查 Redis

确保 Redis 正在运行：
```bash
redis-cli ping
# 应该返回 PONG
```

### 步骤 3：重启 Celery Worker

停止现有 Worker，重新启动：

```bash
# Windows 找到并停止 celery 进程
taskkill /F /IM celery.exe

# 重新启动
cd backend
celery -A app.tasks.celery_app worker --loglevel=info -P solo
```

### 步骤 4：检查数据库

查看任务状态：
```sql
-- 使用 SQLite 浏览器或命令行
SELECT id, status, progress, error_message FROM generation_jobs ORDER BY created_at DESC LIMIT 5;
```

---

## 针对 Hugging Face 的特殊处理

Hugging Face Inference API 有以下限制：

1. **首次加载慢**：10-20 秒模型加载时间
2. **会休眠**：一段时间不用后模型休眠，下次调用需重新加载
3. **速率限制**：免费版约 1 请求/秒

**解决方案**：

### 方案 A：增加任务超时时间

修改 `backend/app/tasks/generation_task.py`：

```python
# 增加超时时间
@shared_task(bind=True, max_retries=3, soft_time_limit=3600, time_limit=3600)
```

### 方案 B：使用 Replicate（推荐）

Replicate 更稳定，不会休眠：
- 注册 https://replicate.com
- 充值 $5（送 $5 免费额度）
- 使用 FLUX Schnell 模型

### 方案 C：本地部署

完全免费，无限制：
```bash
git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui.git
cd stable-diffusion-webui
.\webui.bat --api
```

---

## 调试信息收集

如果以上方法都无效，请收集以下信息：

1. **Celery Worker 日志**（完整输出）
2. **后端日志**（启动后端的终端输出）
3. **浏览器 Network 请求**（开发者工具截图）
4. **任务列表状态**（数据库查询结果）

---

## 常见问题

### Q: 预览成功但批量失败？

预览和批量使用不同的机制：
- 预览：同步 HTTP 请求，5 秒超时
- 批量：异步 Celery 任务，后台执行

可能原因：
- Celery Worker 没有正确配置
- 异步执行时 API 调用超时

### Q: 任务显示"运行中"但进度为 0？

可能原因：
1. 任务卡在第一次 API 调用
2. Hugging Face 模型正在加载（等 1-2 分钟）
3. 任务抛异常但没有更新状态

### Q: 如何取消卡住的任务？

1. 重启 Celery Worker
2. 在数据库中更新任务状态：
```sql
UPDATE generation_jobs SET status = 'cancelled' WHERE status = 'running';
```

---

## 推荐配置

### 稳定生成配置（Replicate）

```yaml
API 地址: https://api.replicate.com/v1/predictions
API 密钥: r8_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Replicate 模型版本: black-forest-labs/flux-schnell
生成数量: 100
```

### 免费测试配置（Hugging Face）

```yaml
API 地址: https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell
API 密钥: hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
生成数量: 5  # 先测试少量
```

---

*最后更新：2026-04-08*
