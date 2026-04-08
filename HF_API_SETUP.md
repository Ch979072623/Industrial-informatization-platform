# Hugging Face Inference API 可用模型列表

## 错误说明

**410 Gone** - 模型不存在或 Inference API 未启用

**503 Service Unavailable** - 模型加载中或需要付费

---

## 推荐的可用模型

### 免费且稳定的模型

| 模型 | API 地址 | 说明 |
|------|---------|------|
| **runwayml/stable-diffusion-v1-5** | `https://api-inference.huggingface.co/models/runwayml/stable-diffusion-v1-5` | ✅ 最稳定，推荐 |
| **stabilityai/stable-diffusion-2-1** | `https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-2-1` | ✅ 质量较好 |
| **segmind/SSD-1B** | `https://api-inference.huggingface.co/models/segmind/SSD-1B` | ✅ 速度更快 |

---

## 推荐配置

### 方案 1：SD 1.5（最稳定）

```yaml
API 地址: https://api-inference.huggingface.co/models/runwayml/stable-diffusion-v1-5
API 密钥: hf_xxxxxxxxxxxxxxxxxxxxxxxx（你的 HuggingFace Token）

生成提示词: a scratch defect on white metal surface, industrial quality inspection, detailed
负向提示词: blurry, low quality, text, watermark, person, face
推理步数: 25
引导强度: 7.5
图像尺寸: 512x512
```

### 方案 2：SD 2.1（质量更好）

```yaml
API 地址: https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-2-1
API 密钥: hf_xxxxxxxxxxxxxxxxxxxxxxxx

生成提示词: a deep scratch on brushed aluminum surface, industrial defect, macro photography
负向提示词: blurry, low quality, text, watermark
推理步数: 30
引导强度: 7.5
图像尺寸: 512x512
```

---

## Hugging Face Token 获取步骤

1. 访问 [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
2. 点击 **"New token"**
3. 选择 Role: **"Read"** 或 **"Write"**
4. 复制以 `hf_` 开头的 Token

---

## 免费版限制

- **速率限制**：约 1 请求/秒
- **等待时间**：首次请求需要 10-30 秒加载模型
- **并发限制**：同时只能有一个请求
- **模型加载**：一段时间不用后模型会休眠，再次请求需要重新加载

---

## 本地部署方案（完全免费无限制）

如果 Hugging Face 体验不佳，强烈推荐本地部署：

### Windows 快速安装

```powershell
# 1. 下载 AUTOMATIC1111
git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui.git

# 2. 进入目录
cd stable-diffusion-webui

# 3. 下载模型（放在 models/Stable-diffusion/ 目录）
# 推荐模型：https://civitai.com/models/30259/realistic-vision-v51

# 4. 启动（带 API 模式）
./webui.bat --api --listen
```

### 系统配置

```yaml
API 地址: http://localhost:7860/sdapi/v1/txt2img
API 密钥: （留空）

生成提示词: a scratch defect on white metal surface
负向提示词: blurry, low quality, text
推理步数: 20
图像尺寸: 512x512
```

### 优点
- ✅ 完全免费，无限制
- ✅ 速度快（本地 GPU）
- ✅ 支持 ControlNet
- ✅ 可自定义模型

### 硬件要求
- NVIDIA GPU，显存 4GB+（推荐 8GB）
- 或 CPU 模式（慢但可用）

---

## 测试脚本

```python
import requests

API_URL = "https://api-inference.huggingface.co/models/runwayml/stable-diffusion-v1-5"
headers = {"Authorization": "Bearer hf_xxxxxxxxxxxxxxxxxxxxxxxx"}

def query(payload):
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.content

image_bytes = query({
    "inputs": "a scratch on metal surface",
})

# 保存图片
with open("test.png", "wb") as f:
    f.write(image_bytes)
```

---

## 模型状态检查

访问以下链接查看模型是否可用：
- https://api-inference.huggingface.co/status

或直接在浏览器访问：
```
https://api-inference.huggingface.co/models/runwayml/stable-diffusion-v1-5
```

返回 200 表示可用，410/503 表示不可用。
