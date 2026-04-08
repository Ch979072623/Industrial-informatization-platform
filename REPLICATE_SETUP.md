# Replicate API 设置指南

## 错误代码说明

| 错误 | 含义 | 解决方案 |
|------|------|---------|
| **401 Unauthorized** | API 密钥无效或账户未激活 | 检查密钥，确认邮箱验证 |
| **402 Payment Required** | 账户需要充值 | 绑定支付方式或充值 |
| **429 Too Many Requests** | 请求太频繁 | 等待几秒再试 |

---

## 完整设置步骤

### 第一步：确认邮箱验证

1. 登录 [replicate.com](https://replicate.com)
2. 检查邮箱是否有验证邮件
3. 点击验证链接完成验证

### 第二步：获取正确的 API Token

1. 访问 [replicate.com/account/api-tokens](https://replicate.com/account/api-tokens)
2. 点击 **"Create a new token"**
3. 复制以 `r8_` 开头的完整字符串

**Token 格式示例**：
```
r8_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

⚠️ **注意**：
- Token 只会显示一次，请妥善保存
- 如果丢失，需要重新创建
- 不要分享给他人

### 第三步：充值（解决 402 错误）

**2024 年起，Replicate 新账户需要预充值才能使用 API**

1. 访问 [replicate.com/account/billing](https://replicate.com/account/billing)
2. 点击 **"Add payment method"**
3. 绑定信用卡或使用其他支付方式
4. 充值至少 **$5**（最低充值金额）

**免费额度说明**：
- 新用户有 **$5 免费额度**
- 但需要先绑定支付方式才能激活
-  FLUX Schnell 约 $0.003/张，可生成约 1500 张

---

## 免费替代方案

如果你暂时不想充值，可以使用以下**完全免费**的替代方案：

### 方案 1：Hugging Face Inference API（免费）

| 配置项 | 值 |
|--------|-----|
| API 地址 | `https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0` |
| API 密钥 | 从 [hf.co/settings/tokens](https://huggingface.co/settings/tokens) 获取 |

**限制**：
- 免费版有速率限制（约 1 请求/秒）
- 高峰期可能需要等待
- 适合小批量测试

---

### 方案 2：本地 AUTOMATIC1111 WebUI（完全免费）

**步骤 1：安装 WebUI**

```bash
# 克隆仓库
git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui.git
cd stable-diffusion-webui

# 启动（添加 --api 参数启用 API）
./webui.sh --api  # Linux/Mac
webui-user.bat --api  # Windows
```

**步骤 2：在系统中配置**

| 配置项 | 值 |
|--------|-----|
| API 地址 | `http://localhost:7860/sdapi/v1/txt2img` |
| API 密钥 | 留空 |

**优点**：
- ✅ 完全免费，无限制
- ✅ 无需网络，本地运行
- ✅ 支持 ControlNet 等高级功能

**缺点**：
- ❌ 需要 NVIDIA GPU（推荐 8GB+ 显存）
- ❌ 首次下载模型需要时间和磁盘空间

---

### 方案 3：Google Colab（免费 GPU）

使用 Colab 运行 Stable Diffusion，然后通过 ngrok 暴露 API：

[Colab Stable Diffusion API 教程](https://colab.research.google.com/drive/xxxxxxxx)

---

## 推荐方案

| 场景 | 推荐方案 | 成本 |
|------|---------|------|
| 快速测试，不想安装 | Hugging Face | 免费（有限制）|
| 大量生成，有 GPU | 本地 A1111 | 免费（电费）|
| 便捷稳定，商用 | Replicate | $0.003-0.05/张 |

---

## 快速验证 Token 是否有效

### 使用 curl 测试

```bash
# 替换为你的实际 token
curl -s -X GET \
  -H "Authorization: Token r8_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
  https://api.replicate.com/v1/account
```

**返回用户信息** → Token 有效，账户正常  
**返回 401** → Token 错误或账户未验证  
**返回 402** → 需要充值

### 使用 Python 测试

```python
import requests

token = "r8_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
response = requests.get(
    "https://api.replicate.com/v1/account",
    headers={"Authorization": f"Token {token}"}
)

print(f"状态码: {response.status_code}")
if response.status_code == 200:
    print(f"用户名: {response.json().get('username')}")
    print(f"邮箱: {response.json().get('email')}")
elif response.status_code == 401:
    print("Token 无效或账户未验证")
elif response.status_code == 402:
    print("账户需要充值")
```

---

## 联系我们

如果仍有问题，请检查：
1. 邮箱是否已验证
2. Token 是否完整复制（包含 `r8_` 前缀）
3. 账户是否已充值或绑定支付方式
