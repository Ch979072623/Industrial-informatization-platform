# Hugging Face 403 Forbidden 错误解决

## 错误原因

**403 Forbidden** 表示你的 Token 没有权限访问该模型。

常见原因：
1. **未接受模型协议** - 需要先同意模型的使用条款
2. **Token 权限不足** - 需要使用 `Read` 权限的 Token
3. **Token 格式错误** - 需要包含 `hf_` 前缀

---

## 解决步骤

### 第一步：确认 Token 格式正确

你的 Token 应该是这种格式：
```
hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**检查方式**：
1. 访问 https://huggingface.co/settings/tokens
2. 确认 Token 以 `hf_` 开头
3. 如果不确定，**删除旧 Token 并创建新 Token**

---

### 第二步：接受模型使用协议（关键）

**这是最常见的原因！**

对于每个你想使用的模型，都必须先在网页端接受其使用条款：

#### SD 1.5
1. 访问 https://huggingface.co/runwayml/stable-diffusion-v1-5
2. 如果看到黄色提示框："Access to model... is restricted", 点击 **"Access repository"**
3. 阅读并勾选 "I have read and agree to the license"
4. 点击 **"Access repository"** 按钮

#### SD 2.1
1. 访问 https://huggingface.co/stabilityai/stable-diffusion-2-1
2. 同样步骤接受协议

---

### 第三步：创建新 Token（推荐）

如果已接受协议还是 403，尝试创建新 Token：

1. 访问 https://huggingface.co/settings/tokens
2. 点击 **"New token"**
3. **Token name**: `defect-detection` (任意名称)
4. **Role**: 选择 **"Read"** 或 **"Write"**
5. 点击 **"Generate a token"**
6. **立即复制并保存**（Token 只显示一次）
7. 在系统中使用新 Token

---

### 第四步：验证 Token 是否有效

使用以下脚本测试：

```python
import requests

token = "hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # 替换为你的 Token
model = "runwayml/stable-diffusion-v1-5"
url = f"https://router.huggingface.co/hf-inference/models/{model}"

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# 测试请求
response = requests.post(
    url,
    headers=headers,
    json="a test image",
    timeout=30
)

print(f"状态码: {response.status_code}")

if response.status_code == 200:
    print("✅ 成功！可以生成图像")
elif response.status_code == 403:
    print("❌ 403 错误 - 需要接受模型协议")
    print(f"请访问: https://huggingface.co/{model}")
elif response.status_code == 401:
    print("❌ 401 错误 - Token 无效")
elif response.status_code == 503:
    print("⏳ 503 错误 - 模型正在加载，稍后再试")
else:
    print(f"其他错误: {response.text[:200]}")
```

---

## 快速检查清单

- [ ] Token 以 `hf_` 开头
- [ ] Token 未过期
- [ ] 已访问 https://huggingface.co/runwayml/stable-diffusion-v1-5 并接受协议
- [ ] Token 有 "Read" 权限
- [ ] 使用的是 `router.huggingface.co` 新地址（不是旧的 `api-inference`）

---

## 替代方案

如果 Hugging Face 实在搞不定，推荐以下方案：

### 方案 1：使用 Google Colab（免费 GPU）

在 Colab 上运行 Stable Diffusion 并通过 ngrok 暴露 API。

### 方案 2：本地部署（完全免费）

```bash
# 快速安装 A1111
git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui.git
cd stable-diffusion-webui

# Windows
.\webui.bat --api

# 然后配置
# API 地址: http://localhost:7860/sdapi/v1/txt2img
# API 密钥: （留空）
```

### 方案 3：充值 Replicate（$5 起）

最简单稳定，FLUX 模型速度快。

---

## 常见问题

### Q: 我已经接受了协议，还是 403？
**A**: 尝试：
1. 创建新的 Token（旧的可能有缓存问题）
2. 清除浏览器缓存，重新登录 Hugging Face
3. 等待 5-10 分钟后重试

### Q: 访问模型页面没有 "Access repository" 按钮？
**A**: 说明你已经接受过协议了，问题可能在 Token。尝试创建新 Token。

### Q: 提示 "You need to authenticate"？
**A**: Token 格式错误或已失效。重新创建 Token 并确保完整复制。

---

## 推荐配置

### 方案 A：FLUX Schnell（推荐，无需协议）

```yaml
API 提供商: HuggingFace FLUX Schnell ⭐
API 地址: https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell
API 密钥: hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx（你的 Token）

生成提示词: a scratch defect on white metal surface
负向提示词: （可留空，FLUX 不支持）
推理步数: 4
图像尺寸: 1024x1024  # FLUX 默认输出 1024x1024，设置无效
```

**优点**：
- ✅ 4步出图，速度极快
- ✅ 无需接受模型协议
- ✅ 图像质量高

**⚠️ 重要：首次使用会超时！**

Hugging Face 首次加载模型需要 **10-20 秒**，而我们的预览有 5 秒限制，所以：

1. 第一次点击 **"生成预览"** → 会显示超时（正常现象！）
2. 等待 10-15 秒，模型加载完成
3. 再次点击 **"生成预览"** → 这次会成功，2-4 秒出图！

**或者**：直接执行批量生成（无 5 秒限制，后台会等待模型加载完成）

**注意**：
- FLUX 通过 Hugging Face 的调用**不支持自定义参数**（步数、尺寸等）
- 只需要提供 **prompt** 即可
- 图像尺寸固定为 1024x1024

### 方案 B：SD 1.5（需接受协议）

```yaml
API 提供商: HuggingFace SD 1.5
API 地址: https://router.huggingface.co/hf-inference/models/runwayml/stable-diffusion-v1-5
API 密钥: hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx（你的新 Token）

生成提示词: a scratch defect on white metal surface
负向提示词: blurry, low quality, text, watermark
推理步数: 25
图像尺寸: 512x512
```

**注意**：使用前必须访问 https://huggingface.co/runwayml/stable-diffusion-v1-5 接受协议

---

*最后更新：2026-04-08*
