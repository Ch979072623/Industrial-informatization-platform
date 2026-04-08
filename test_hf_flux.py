#!/usr/bin/env python3
"""测试 Hugging Face FLUX API"""

import requests

url = 'https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell'
token = input("请输入你的 HuggingFace Token (hf_...): ").strip()

headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

prompt = "a scratch defect on white metal surface"

# 测试 1: 只发送字符串
print('\nTest 1: 发送字符串')
try:
    r = requests.post(url, headers=headers, json=prompt, timeout=30)
    print(f'  Status: {r.status_code}')
    print(f'  Content-Type: {r.headers.get("content-type")}')
    if r.status_code == 200:
        print('  ✅ 成功！')
    else:
        print(f'  Response: {r.text[:300]}')
except Exception as e:
    print(f'  Error: {e}')

# 测试 2: 发送 inputs 格式  
print('\nTest 2: 发送 {"inputs": ...}')
try:
    r = requests.post(url, headers=headers, json={"inputs": prompt}, timeout=30)
    print(f'  Status: {r.status_code}')
    if r.status_code == 200:
        print('  ✅ 成功！')
    else:
        print(f'  Response: {r.text[:300]}')
except Exception as e:
    print(f'  Error: {e}')

# 测试 3: 发送带参数的格式  
print('\nTest 3: 发送 {"inputs": ..., "parameters": ...}')
try:
    r = requests.post(url, headers=headers, json={
        "inputs": prompt,
        "parameters": {"num_inference_steps": 4}
    }, timeout=30)
    print(f'  Status: {r.status_code}')
    if r.status_code == 200:
        print('  ✅ 成功！')
    else:
        print(f'  Response: {r.text[:300]}')
except Exception as e:
    print(f'  Error: {e}')

print('\n测试完成')
