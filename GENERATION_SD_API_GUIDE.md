# Stable Diffusion API 生成器使用指南

本文档介绍如何使用基于 Stable Diffusion 的 API 生成器进行文生图（Text-to-Image）数据生成。

---

## 目录

1. [支持的 API 提供商](#支持的-api-提供商)
2. [快速开始（Replicate）](#快速开始replicate)
3. [配置参数说明](#配置参数说明)
4. [提示词编写指南](#提示词编写指南)
5. [常见问题](#常见问题)

---

## 支持的 API 提供商

### 1. Replicate（推荐，最易用）

**适用场景**：不想本地部署，直接使用云端高性能 GPU

| 配置项 | 值 |
|--------|-----|
| **API 地址** | `https://api.replicate.com/v1/predictions` |
| **API 密钥** | 从 [replicate.com/account/api-tokens](https://replicate.com/account/api-tokens) 获取 |

**特点**：
- ✅ 无需本地 GPU，云端生成
- ✅ 支持多种模型（SDXL、FLUX 等）
- ✅ 按需付费，新用户有免费额度
- ✅ 国内访问可能需要代理

**获取密钥步骤**：
1. 访问 [replicate.com](https://replicate.com) 注册账号
2. 进入 Account Settings → API Tokens
3. 点击 "Create a new token"
4. 复制以 `r8_` 开头的 Token

---

### 2. AUTOMATIC1111 WebUI（本地/自托管）

**适用场景**：已有本地或远程部署的 A1111 WebUI

| 配置项 | 值 |
|--------|-----|
| **API 地址** | `http://localhost:7860/sdapi/v1/txt2img` |
| **API 密钥** | 留空（除非在 WebUI 中设置了 API 认证）|

**前置条件**：
- 启动 WebUI 时需要添加 `--api` 参数
- 例如：`python launch.py --api`

**远程服务器**：
如果 WebUI 部署在其他机器上，将 `localhost` 替换为服务器 IP：
```
http://192.168.1.100:7860/sdapi/v1/txt2img
```

---

### 3. Stability AI（官方 API）

**适用场景**：需要商业级稳定性，官方原生支持

| 配置项 | 值 |
|--------|-----|
| **API 地址** | `https://api.stability.ai/v2beta/stable-image/generate/sd3` |
| **API 密钥** | 从 [platform.stability.ai](https://platform.stability.ai/api-keys) 获取 |

**特点**：
- ✅ 官方原生 API，稳定可靠
- ✅ 新用户有免费试用额度
- ❌ 价格相对较高

---

### 4. Hugging Face Inference API

**适用场景**：使用开源社区模型，成本敏感

| 配置项 | 值 |
|--------|-----|
| **API 地址** | `https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0` |
| **API 密钥** | 从 [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) 获取 |

**注意**：免费版有速率限制，高峰期可能需要等待

---

## 快速开始（Replicate）

### 第一步：注册并获取密钥

1. 访问 [replicate.com](https://replicate.com)
2. 使用 GitHub 或邮箱注册
3. 进入 [API Tokens 页面](https://replicate.com/account/api-tokens)
4. 创建新 Token，复制以 `r8_` 开头的字符串

### 第二步：在系统中配置

**数据生成页面 → 选择 "Stable Diffusion API 生成器" → 填写配置**：

**推荐配置（FLUX Schnell，速度最快）**：

```yaml
API 地址: https://api.replicate.com/v1/predictions
API 密钥: r8_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx  # 你的实际密钥
Replicate 模型版本: black-forest-labs/flux-schnell

生成提示词: a scratch defect on white metal surface, industrial quality inspection, macro photography, high detail, realistic texture, studio lighting

# FLUX 不需要负向提示词和复杂参数
推理步数: 4  # FLUX 只需 4 步，SD 需要 50 步
图像尺寸: 1024x1024  # FLUX 默认高分辨率
```

**传统配置（SDXL，兼容性更好）**：

```yaml
API 地址: https://api.replicate.com/v1/predictions
API 密钥: r8_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Replicate 模型版本: stability-ai/stable-diffusion-xl-base-1.0

生成提示词: a scratch defect on white metal surface, industrial quality inspection, macro photography, high detail

负向提示词: blurry, low quality, text, watermark, logo, person, face, cartoon, painting
推理步数: 20  # 降低步数以避免超时
引导强度: 7.5
图像尺寸: 512x512
```

### 第三步：生成测试

1. 点击"生成预览"测试单张图像
2. 确认效果后，设置生成数量（建议先测试 10-20 张）
3. 点击"开始生成"提交任务

---

## 配置参数说明

### 必填参数

| 参数名 | 说明 | 示例 |
|--------|------|------|
| `api_endpoint` | API 端点地址 | `https://api.replicate.com/v1/predictions` |
| `prompt` | 生成提示词，描述想要的图像内容 | `a scratch on metal surface` |

### 可选参数

| 参数名 | 默认值 | 范围 | 说明 |
|--------|--------|------|------|
| `api_key` | - | - | API 认证密钥 |
| `replicate_version` | `flux-schnell` | - | **Replicate 模型选择（关键参数）** |
| `negative_prompt` | `blurry, low quality...` | - | 不希望出现的内容 |

#### 模型选择建议（`replicate_version`）

| 模型 | 速度 | 质量 | 成本 | 适用场景 |
|------|------|------|------|---------|
| **FLUX Schnell** ⭐ | 极快 (~2s) | 高 | 低 | **推荐，性价比最高** |
| FLUX 1.1 Pro | 中等 (~10s) | 极高 | 高 | 需要最高质量时 |
| FLUX Dev | 快 (~5s) | 很高 | 中 | 质量与速度平衡 |
| SDXL Base | 慢 (~15s) | 高 | 中 | 传统选择，兼容性好 |
| SD 1.5 | 较慢 (~20s) | 中 | 低 | 经典模型，资源占用小 |

**FLUX 优势**：
- ✅ **4步出图**，比 SD 快 10 倍
- ✅ 对提示词理解更好，遵循更精确
- ✅ 默认 1024x1024 高分辨率
- ✅ 无需复杂的负向提示词
- ✅ 价格更便宜（速度快 = 成本低）
| `num_inference_steps` | 50 | 10-100 | 推理步数，越高细节越丰富但越慢 |
| `guidance_scale` | 7.5 | 1.0-20.0 | 提示词遵循程度，越高越严格 |
| `image_size.width` | 512 | 256/512/768/1024 | 图像宽度 |
| `image_size.height` | 512 | 256/512/768/1024 | 图像高度 |
| `timeout` | 30 | 10-300 | 请求超时时间（秒）|
| `max_retries` | 3 | 0-5 | 失败重试次数 |
| `seed` | - | ≥-1 | 随机种子，-1 表示随机，固定值可复现结果 |
| `sampler` | DPM++ 2M Karras | - | 采样算法（仅 A1111）|

### 高级参数（ControlNet）

| 参数名 | 默认值 | 说明 |
|--------|--------|------|
| `use_controlnet` | false | 是否使用 ControlNet 控制生成结构 |
| `controlnet_image` | - | 参考图像（Base64 编码）|
| `controlnet_model` | canny | 预处理器类型：canny/depth/pose/scribble |
| `controlnet_strength` | 1.0 | 控制强度，0-2，越高控制越强 |

---

## 提示词编写指南

### 工业缺陷生成提示词模板

```
[缺陷类型] on [背景表面], industrial quality inspection, [摄影风格], [光照条件], [质量修饰词]
```

### 常用缺陷类型关键词

| 缺陷 | 英文关键词 |
|------|-----------|
| 划痕 | scratch, scrape, abrasion |
| 裂纹 | crack, fracture, fissure |
| 凹坑 | dent, pit, indentation, cavity |
| 锈蚀 | rust, corrosion, oxidation |
| 污渍 | stain, contamination, smudge |
| 变形 | deformation, warp, bend |
| 缺料 | missing material, chip, notch |
| 气泡 | bubble, blister, void |
| 色差 | color difference, discoloration |

### 表面类型关键词

| 表面 | 英文关键词 |
|------|-----------|
| 金属 | metal, aluminum, steel, copper |
| 塑料 | plastic, polymer, PVC |
| 陶瓷 | ceramic, porcelain |
| 玻璃 | glass, transparent |
| 木材 | wood, timber, wooden |
| 布料 | fabric, textile, cloth |
| 电路板 | PCB, circuit board, electronic |

### 完整示例

**示例 1：金属表面划痕**
```
a deep scratch on brushed aluminum surface, industrial quality inspection, macro photography, directional lighting from left, high detail, realistic texture, 8k resolution, sharp focus
```

**示例 2：电路板缺陷**
```
a cold solder joint defect on green PCB, electronic component, industrial inspection, top-down view, uniform lighting, high magnification, sharp details, no blur
```

**示例 3：玻璃气泡**
```
air bubbles in transparent glass panel, optical defect, bright field illumination, high contrast, microscopic view, circular bubble patterns
```

**示例 4：塑料色差**
```
color inconsistency patch on white plastic surface, injection molding defect, diffuse lighting, flat lay photography, texture detail
```

### 负向提示词推荐

```
blurry, low quality, text, watermark, logo, signature, person, face, body, cartoon, illustration, painting, drawing, artificial, synthetic look, noise, grain, overexposed, underexposed
```

---

## Replicate 模型选择

系统默认使用 `stability-ai/stable-diffusion`，但你可以在 Replicate 上选择其他模型：

### 修改模型版本

如需使用特定模型，需要修改后端代码中的版本 ID：

**文件**: `backend/app/ml/generation/stable_diffusion_api.py`

**第 264 行附近**，修改 `version` 字段：

```python
# 使用 SDXL
"version": "stability-ai/stable-diffusion-xl-base-1.0:xxxxxx"

# 使用 FLUX
"version": "black-forest-labs/flux-schnell"

# 使用其他模型，从 Replicate 模型页面获取版本号
```

### 热门模型推荐

| 模型 | 适用场景 | 版本号示例 |
|------|---------|-----------|
| SDXL | 通用高质量生成 | `stability-ai/stable-diffusion-xl-base-1.0` |
| FLUX Schnell | 快速生成，4步出图 | `black-forest-labs/flux-schnell` |
| FLUX Pro | 最高质量 | `black-forest-labs/flux-2-pro` |

---

## 常见问题

### Q1: 429 Too Many Requests 错误

**原因**：Replicate 对免费用户有速率限制，短时间内请求过多

**解决**：
1. **改用 FLUX Schnell 模型**（推荐）
   - 生成速度快 10 倍，大幅降低触发限制的概率
   - 在配置中选择 `"black-forest-labs/flux-schnell"`

2. **降低请求频率**
   - 批量生成时减少并发数量
   - 两次生成之间间隔几秒

3. **升级 Replicate 账户**
   - 付费用户有更高的速率限制
   - 访问 [replicate.com/pricing](https://replicate.com/pricing)

4. **使用本地部署**
   - 本地 A1111 WebUI 没有速率限制

---

### Q2: 预览生成超时（5秒）

**原因**：API 请求需要一定时间，超过预览的 5 秒限制

**解决**：
- **使用 FLUX Schnell 模型**（4步出图，通常 2-3 秒完成）
- 直接执行批量生成（后台任务无 5 秒限制）
- 使用本地 A1111 WebUI 减少网络延迟
- 降低 `num_inference_steps` 到 10-20

### Q3: 生成的图像质量不佳

**优化建议**：
1. 增加 `num_inference_steps` 到 50-75
2. 调整 `guidance_scale` 到 7-9
3. 优化提示词，增加质量关键词如 `8k, highly detailed, professional photography`
4. 使用更精确的负向提示词

### Q4: 生成任务失败

**排查步骤**：
1. 检查 API 密钥是否正确（是否有多余空格）
2. 检查 API 地址是否完整（需要包含 `https://`）
3. 查看后端日志获取详细错误信息
4. 测试 API 是否可用（使用 curl 或 Postman）

### Q5: 如何降低使用成本

**Replicate 省钱技巧**：
- 使用 `flux-schnell` 模型（4步出图，速度快 10 倍）
- 降低 `num_inference_steps`（30步通常已足够）
- 批量生成时选择较小的图像尺寸（512x512 比 1024x1024 便宜 4 倍）

### Q6: 生成的缺陷不真实

**改进方向**：
- 在提示词中加入 `realistic, macro photography, industrial inspection`
- 使用 ControlNet 配合真实缺陷边缘图
- 尝试不同种子找到最佳效果
- 使用缺陷迁移生成器（Defect Migration）替代

---

## API 调用示例（Replicate）

### Python 测试代码

```python
import requests
import base64

# 配置
api_key = "r8_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
url = "https://api.replicate.com/v1/predictions"

# 请求体
payload = {
    "version": "stability-ai/stable-diffusion:ac732df83cea7fff18b8472768c88ad041fa750ff7682a21affe81863cbe77e4",
    "input": {
        "prompt": "a scratch defect on white metal surface, industrial inspection",
        "negative_prompt": "blurry, low quality, text, watermark, person",
        "num_inference_steps": 50,
        "guidance_scale": 7.5,
        "width": 512,
        "height": 512
    }
}

headers = {
    "Authorization": f"Token {api_key}",
    "Content-Type": "application/json"
}

# 发送请求
response = requests.post(url, json=payload, headers=headers)
result = response.json()

print("预测 ID:", result.get("id"))
print("状态:", result.get("status"))
print("轮询 URL:", result.get("urls", {}).get("get"))
```

### cURL 测试

```bash
curl -X POST https://api.replicate.com/v1/predictions \
  -H "Authorization: Token r8_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "version": "stability-ai/stable-diffusion:ac732df83cea7fff18b8472768c88ad041fa750ff7682a21affe81863cbe77e4",
    "input": {
      "prompt": "a scratch defect on metal surface",
      "num_inference_steps": 50,
      "guidance_scale": 7.5
    }
  }'
```

---

## 相关文档

- [Replicate API 文档](https://replicate.com/docs/reference/http)
- [Stability AI API 文档](https://platform.stability.ai/docs/api-reference)
- [A1111 WebUI API 文档](https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/API)

---

*最后更新：2026-04-08*
