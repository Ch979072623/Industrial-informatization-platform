# Stable Diffusion API 提供商配置指南

## 2024 年 4 月更新

Hugging Face 已更新为 **Router API**，旧地址 `api-inference.huggingface.co` 已停用。

---

## 推荐的 API 提供商

### 1. Replicate ⭐ 推荐（速度最快）

| 配置项 | 值 |
|--------|-----|
| **API 地址** | `https://api.replicate.com/v1/predictions` |
| **API 密钥** | `r8_` 开头的 Token |
| **模型版本** | `black-forest-labs/flux-schnell` |
| **成本** | 约 $0.003/张（FLUX Schnell）|
| **速度** | 2-4 秒/张 |
| **限制** | 需充值（最低 $5）|

**优点**：
- ✅ 速度极快（FLUX 4步出图）
- ✅ 支持多种模型
- ✅ 稳定可靠

**缺点**：
- ❌ 需要绑定信用卡充值

---

### 2. Hugging Face Router API（免费）

| 配置项 | 值 |
|--------|-----|
| **API 地址** | `https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell` |
| **API 密钥** | `hf_` 开头的 Token |
| **成本** | 免费 |
| **速度** | 5-15 秒/张（含模型加载时间）|
| **限制** | 速率限制，模型会休眠 |

**可用模型列表**：

| 模型 | API 地址 | 推荐度 |
|------|---------|--------|
| **FLUX Schnell** ⭐ | `https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell` | **最推荐，4步出图** |
| SD 1.5 | `https://router.huggingface.co/hf-inference/models/runwayml/stable-diffusion-v1-5` | 需接受协议 |
| SD 2.1 | `https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-2-1` | 需接受协议 |

**优点**：
- ✅ 完全免费
- ✅ 无需 GPU

**缺点**：
- ❌ 首次请求需等待模型加载（10-30秒）
- ❌ 有速率限制
- ❌ 模型会休眠，一段时间不用需重新加载

---

### 3. 本地 AUTOMATIC1111（完全免费）

| 配置项 | 值 |
|--------|-----|
| **API 地址** | `http://localhost:7860/sdapi/v1/txt2img` |
| **API 密钥** | 留空 |
| **成本** | 免费（电费）|
| **速度** | 取决于 GPU，约 2-10 秒/张 |
| **限制** | 需 NVIDIA GPU 4GB+ |

**安装步骤**：

```bash
# 克隆仓库
git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui.git
cd stable-diffusion-webui

# Windows: 运行
.\webui.bat --api

# Linux/Mac: 运行
./webui.sh --api
```

**优点**：
- ✅ 完全免费，无限制
- ✅ 可自定义模型
- ✅ 支持 ControlNet

**缺点**：
- ❌ 需要 NVIDIA GPU
- ❌ 首次下载约 4GB 模型文件

---

## 快速配置指南

### Replicate 配置（推荐）

```yaml
API 地址: https://api.replicate.com/v1/predictions
API 密钥: r8_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Replicate 模型版本: black-forest-labs/flux-schnell
生成提示词: a scratch defect on white metal surface
推理步数: 4
图像尺寸: 1024x1024
```

### Hugging Face 配置（免费）- 推荐 FLUX

```yaml
API 地址: https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell
API 密钥: hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
生成提示词: a scratch defect on white metal surface
负向提示词: （FLUX 可忽略）
推理步数: 4
图像尺寸: 1024x1024
```

**⚠️ HuggingFace 重要提示**：
- ✅ **首次请求会超时**，因为模型需要 10-20 秒加载，这是正常现象！
- ✅ **点击"生成预览"后等待超时，然后再次点击即可成功**
- FLUX Schnell **4步出图**，速度比 SD 快 10 倍
- 一段时间不用后模型会休眠
- SD 1.5/2.1 需要先在 HF 网站接受协议（见下方）

### Hugging Face SD 配置（备选）

```yaml
API 地址: https://router.huggingface.co/hf-inference/models/runwayml/stable-diffusion-v1-5
API 密钥: hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
生成提示词: a scratch defect on white metal surface
负向提示词: blurry, low quality, text, watermark
推理步数: 25
图像尺寸: 512x512
```

**⚠️ 使用 SD 模型前必须**：
1. 访问 https://huggingface.co/runwayml/stable-diffusion-v1-5
2. 点击 "Access repository" 接受协议

### 本地 A1111 配置

```yaml
API 地址: http://localhost:7860/sdapi/v1/txt2img
API 密钥: （留空）
生成提示词: a scratch defect on white metal surface
负向提示词: blurry, low quality, text
推理步数: 20
图像尺寸: 512x512
```

---

## 常见错误及解决

### 401 Unauthorized
- **Replicate**：Token 错误或账户未验证邮箱
- **HuggingFace**：Token 错误或已过期

### 402 Payment Required
- **Replicate**：账户需要充值（最低 $5）
- **解决**：访问 https://replicate.com/account/billing

### 410 Gone
- **HuggingFace**：使用了旧的 API 地址
- **解决**：改为 `https://router.huggingface.co/hf-inference/models/...`

### 429 Too Many Requests
- **原因**：请求太频繁
- **解决**：降低请求频率，或升级账户

### 503 Service Unavailable
- **HuggingFace**：模型正在加载或服务器繁忙
- **解决**：等待 10-20 秒后重试

### 202 Accepted
- **HuggingFace**：模型正在加载（正常现象）
- **解决**：系统会自动等待，请耐心等候

---

## 推荐方案选择

| 你的情况 | 推荐方案 | 理由 |
|---------|---------|------|
| 追求速度稳定，愿付费 | Replicate | 最快最稳定 |
| 不想付费，偶尔使用 | HuggingFace | 免费够用 |
| 有 NVIDIA GPU | 本地 A1111 | 完全免费无限制 |
| 商用生产环境 | Replicate | 可靠性最高 |

---

## API 密钥获取

### Replicate
1. https://replicate.com/account/api-tokens
2. 创建 Token（以 `r8_` 开头）

### HuggingFace
1. https://huggingface.co/settings/tokens
2. 创建 Read 权限 Token（以 `hf_` 开头）

---

*最后更新：2026-04-08*
