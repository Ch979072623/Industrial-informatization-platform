import os
import requests
from typing import List
from huggingface_hub import HfApi

# ================= 配置区 =================
TOKEN = ""
MODELS = [
    "black-forest-labs/FLUX.1-schnell",
    "runwayml/stable-diffusion-v1-5",
    "stabilityai/stable-diffusion-2-1",
    "segmind/SSD-1B",
    "stabilityai/stable-diffusion-3.5-large",
]
TEST_PROMPT = "a cat"
TIMEOUT = 30
# ===========================================

def test_model(model_id: str, token: str) -> None:
    # 关键改动：使用新的路由器域名
    url = f"https://router.huggingface.co/hf-inference/models/{model_id}"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "inputs": TEST_PROMPT,
        "parameters": {
            "width": 64,
            "height": 64,
            "num_inference_steps": 1,
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)

        if response.status_code == 200:
            print(f"✅ {model_id}: 可用")
        elif response.status_code == 503:
            print(f"⏳ {model_id}: 模型加载中")
        elif response.status_code == 401:
            print(f"❌ {model_id}: Token 无效")
        elif response.status_code == 403:
            print(f"❌ {model_id}: 无权限")
        elif response.status_code == 429:
            print(f"⚠️ {model_id}: 请求限流")
        else:
            print(f"⚠️ {model_id}: HTTP {response.status_code} - {response.text[:100]}")
    except Exception as e:
        print(f"💥 {model_id}: {str(e)}")
# 模型API地址
API_URL = "https://router.huggingface.co/hf-inference/models/google/flan-t5-small"
headers = {"Authorization": f"Bearer {TOKEN}"}

# 一个简单的测试问题
def test_flan_t5():
    payload = {
        "inputs": "Please answer the following question: What is the capital of France?",
        "parameters": {
            "max_new_tokens": 50,       # 限制生成长度
            "return_full_text": False   # 只返回新生成的内容
        }
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            # 打印生成的文本
            print("✅ API 调用成功！")
            print(f"回答: {result[0]['generated_text']}")
        else:
            print(f"❌ API 调用失败，状态码: {response.status_code}")
            print(f"错误信息: {response.text}")
    except Exception as e:
        print(f"💥 请求异常: {e}")


def main():
    if not TOKEN or TOKEN == "请在此处填入你的 Token":
        print("❌ 未设置有效的 Hugging Face Token")
        return
    print(f"🚀 测试 {len(MODELS)} 个模型...\n")
    for model in MODELS:
        test_model(model, TOKEN)
    print("\n✅ 测试完成")
    test_flan_t5()



if __name__ == "__main__":
    main()