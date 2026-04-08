"""
Stable Diffusion API 生成器

通过外部 Stable Diffusion API 生成缺陷图像
"""
import os
import io
import cv2
import json
import base64
import logging
import requests
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from PIL import Image

from app.ml.generation.base import BaseGenerator, GenerationResult, GenerationError
from app.ml.generation.registry import register_generator

logger = logging.getLogger(__name__)


@register_generator
class StableDiffusionAPIGenerator(BaseGenerator):
    """
    Stable Diffusion API 生成器
    
    通过外部 Stable Diffusion API 生成缺陷图像
    支持多种 API 提供商（Replicate、Stability AI、自托管等）
    """
    
    _name = "stable_diffusion_api"
    _description = "通过外部 Stable Diffusion API 生成缺陷图像"
    _is_builtin = True
    _supported_formats = ["coco"]  # 扩散模型生成的图像通常用 COCO 格式
    
    def __init__(self):
        super().__init__()
        self.api_endpoint: str = ""
        self.api_key: str = ""
        self.prompt: str = ""
        self.negative_prompt: str = ""
        self.steps: int = 50
        self.guidance: float = 7.5
        self.width: int = 512
        self.height: int = 512
        self.timeout: int = 30
        self.max_retries: int = 3
    
    def get_name(self) -> str:
        return "stable_diffusion_api"
    
    def get_description(self) -> str:
        return "通过外部 Stable Diffusion API 生成缺陷图像"
    
    def get_config_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "api_endpoint": {
                    "type": "string",
                    "title": "API 地址",
                    "description": "选择下方的推荐地址，或使用自定义地址",
                    "format": "uri",
                    "default": "https://api.replicate.com/v1/predictions",
                    "enum": [
                        "https://api.replicate.com/v1/predictions",
                        "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell",
                        "https://router.huggingface.co/hf-inference/models/runwayml/stable-diffusion-v1-5",
                        "https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-2-1",
                        "http://localhost:7860/sdapi/v1/txt2img"
                    ],
                    "enumNames": [
                        "Replicate (推荐，速度快，需付费)",
                        "HuggingFace FLUX Schnell ⭐ (免费，4步出图，快)",
                        "HuggingFace SD 1.5 (免费，需协议)",
                        "HuggingFace SD 2.1 (免费，需协议)",
                        "本地 A1111 (完全免费，需GPU)"
                    ]
                },
                "api_key": {
                    "type": "string",
                    "title": "API 密钥",
                    "format": "password",
                    "description": "API 认证密钥（自托管可留空）"
                },
                "replicate_version": {
                    "type": "string",
                    "title": "Replicate 模型版本（仅 Replicate 有效）",
                    "description": "FLUX 模型速度快，SD 模型兼容性好",
                    "default": "black-forest-labs/flux-schnell",
                    "enum": [
                        "black-forest-labs/flux-schnell",
                        "black-forest-labs/flux-1.1-pro",
                        "black-forest-labs/flux-dev",
                        "stability-ai/stable-diffusion-xl-base-1.0",
                        "stability-ai/stable-diffusion:ac732df83cea7fff18b8472768c88ad041fa750ff7682a21affe81863cbe77e4"
                    ],
                    "enumNames": [
                        "FLUX Schnell (推荐，4步出图，速度快)",
                        "FLUX 1.1 Pro (最高质量)",
                        "FLUX Dev (开发版，质量速度平衡)",
                        "SDXL Base 1.0 (传统模型)",
                        "Stable Diffusion 1.5 (经典模型)"
                    ]
                },
                "prompt": {
                    "type": "string",
                    "title": "生成提示词",
                    "description": "描述要生成的缺陷类型，如 'a scratch on white metal surface, industrial defect, high quality, detailed'",
                    "minLength": 5
                },
                "negative_prompt": {
                    "type": "string",
                    "title": "负向提示词（可选，SD模型有效）",
                    "description": "不希望出现的内容，如 'blurry, low quality, text, watermark'（FLUX模型不支持负向提示）",
                    "default": "blurry, low quality, text, watermark, logo, person, face"
                },
                "num_inference_steps": {
                    "type": "integer",
                    "title": "推理步数（SD模型有效）",
                    "minimum": 4,
                    "maximum": 100,
                    "default": 20,
                    "description": "SD模型建议20-30步，FLUX只需4步（会自动调整）"
                },
                "guidance_scale": {
                    "type": "number",
                    "title": "引导强度",
                    "minimum": 1.0,
                    "maximum": 20.0,
                    "default": 7.5,
                    "description": "提示词遵循程度，越高越严格遵循提示词"
                },
                "image_size": {
                    "type": "object",
                    "title": "图像尺寸",
                    "properties": {
                        "width": {
                            "type": "integer",
                            "enum": [256, 512, 768, 1024],
                            "default": 512
                        },
                        "height": {
                            "type": "integer",
                            "enum": [256, 512, 768, 1024],
                            "default": 512
                        }
                    }
                },
                "use_controlnet": {
                    "type": "boolean",
                    "title": "使用 ControlNet（需要参考图）",
                    "default": False,
                    "description": "使用 ControlNet 控制生成结构"
                },
                "controlnet_image": {
                    "type": "string",
                    "title": "ControlNet 参考图（base64）",
                    "description": "use_controlnet=true 时必填"
                },
                "controlnet_model": {
                    "type": "string",
                    "title": "ControlNet 模型",
                    "default": "canny",
                    "enum": ["canny", "depth", "pose", "scribble"],
                    "description": "ControlNet 预处理器类型"
                },
                "controlnet_strength": {
                    "type": "number",
                    "title": "ControlNet 控制强度",
                    "minimum": 0.0,
                    "maximum": 2.0,
                    "default": 1.0
                },
                "seed": {
                    "type": "integer",
                    "title": "随机种子（可选）",
                    "description": "固定种子可复现结果，-1 表示随机"
                },
                "timeout": {
                    "type": "integer",
                    "title": "请求超时（秒）",
                    "minimum": 10,
                    "maximum": 300,
                    "default": 30
                },
                "max_retries": {
                    "type": "integer",
                    "title": "最大重试次数",
                    "minimum": 0,
                    "maximum": 5,
                    "default": 3
                },
                "sampler": {
                    "type": "string",
                    "title": "采样器",
                    "default": "DPM++ 2M Karras",
                    "enum": [
                        "Euler a",
                        "Euler",
                        "LMS",
                        "Heun",
                        "DPM2",
                        "DPM2 a",
                        "DPM++ 2S a",
                        "DPM++ 2M",
                        "DPM++ 2M Karras",
                        "DPM++ SDE",
                        "DPM++ SDE Karras",
                        "DPM fast",
                        "DPM adaptive",
                        "LMS Karras"
                    ]
                }
            },
            "required": ["api_endpoint", "prompt"]
        }
    
    def _on_configure(self, config: Dict[str, Any]) -> None:
        """配置后的初始化"""
        self.api_endpoint = config["api_endpoint"]
        self.api_key = config.get("api_key", "")
        self.prompt = config["prompt"]
        self.negative_prompt = config.get("negative_prompt", "blurry, low quality, text, watermark")
        self.steps = config.get("num_inference_steps", 50)
        self.guidance = config.get("guidance_scale", 7.5)
        
        size_config = config.get("image_size", {})
        self.width = size_config.get("width", 512)
        self.height = size_config.get("height", 512)
        
        self.timeout = config.get("timeout", 30)
        self.max_retries = config.get("max_retries", 3)
    
    def _detect_api_type(self) -> str:
        """检测 API 类型"""
        endpoint = self.api_endpoint.lower()
        
        if "replicate" in endpoint:
            return "replicate"
        elif "stability" in endpoint or "dreamstudio" in endpoint:
            return "stability"
        elif "huggingface" in endpoint or "hf.co" in endpoint:
            return "huggingface"
        elif "sdapi" in endpoint or "txt2img" in endpoint:
            return "automatic1111"
        else:
            return "generic"
    
    def _make_request(self, attempt: int = 0) -> Dict[str, Any]:
        """
        发送 API 请求
        
        Args:
            attempt: 当前尝试次数
            
        Returns:
            API 响应
        """
        api_type = self._detect_api_type()
        
        try:
            if api_type == "replicate":
                return self._request_replicate()
            elif api_type == "stability":
                return self._request_stability()
            elif api_type == "huggingface":
                return self._request_huggingface()
            elif api_type == "automatic1111":
                return self._request_automatic1111()
            else:
                return self._request_generic()
                
        except requests.Timeout:
            if attempt < self.max_retries:
                logger.warning(f"请求超时，重试 {attempt + 1}/{self.max_retries}")
                import time
                time.sleep(2 ** attempt)  # 指数退避
                return self._make_request(attempt + 1)
            raise TimeoutError(f"API 请求超时（{self.timeout}秒）")
            
        except requests.RequestException as e:
            if attempt < self.max_retries:
                logger.warning(f"请求失败，重试 {attempt + 1}/{self.max_retries}: {e}")
                import time
                time.sleep(2 ** attempt)
                return self._make_request(attempt + 1)
            raise GenerationError(f"API 请求失败: {str(e)}")
    
    def _request_replicate(self) -> Dict[str, Any]:
        """Replicate API 请求"""
        import time
        
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 使用 FLUX Schnell 模型（速度快，4步出图，成本低）
        # 如需更高质量，可改用 "black-forest-labs/flux-1.1-pro"
        version = self._config.get("replicate_version", "black-forest-labs/flux-schnell")
        
        # FLUX 模型的参数与 SD 不同
        if "flux" in version.lower():
            payload = {
                "version": version,
                "input": {
                    "prompt": self.prompt,
                    "aspect_ratio": "1:1",
                    "output_format": "png",
                    "output_quality": 80
                }
            }
        else:
            # 传统 SD 模型参数
            payload = {
                "version": version,
                "input": {
                    "prompt": self.prompt,
                    "negative_prompt": self.negative_prompt,
                    "num_inference_steps": min(self.steps, 30),  # 限制步数避免超时
                    "guidance_scale": self.guidance,
                    "width": self.width,
                    "height": self.height
                }
            }
        
        # 添加种子（如果支持）
        if "seed" in self._config and self._config["seed"] >= 0:
            payload["input"]["seed"] = self._config["seed"]
        
        # 发送请求，带重试逻辑
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                response = requests.post(
                    self.api_endpoint,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout
                )
                
                # 处理 429 速率限制
                if response.status_code == 429:
                    wait_time = 2 ** (attempt + 1)  # 指数退避：2, 4, 8 秒
                    logger.warning(f"Replicate 速率限制，等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                result = response.json()
                
                # Replicate 是异步的，需要轮询结果
                if "urls" in result and "get" in result["urls"]:
                    return self._poll_replicate_result(result["urls"]["get"], headers)
                
                return result
                
            except requests.exceptions.RequestException as e:
                if attempt < max_attempts - 1:
                    wait_time = 2 ** (attempt + 1)
                    logger.warning(f"请求失败，{wait_time} 秒后重试: {e}")
                    time.sleep(wait_time)
                else:
                    raise
        
        raise GenerationError("Replicate 请求多次重试后仍失败")
    
    def _poll_replicate_result(self, poll_url: str, headers: Dict, max_polls: int = 30) -> Dict[str, Any]:
        """轮询 Replicate 结果"""
        import time
        
        poll_count = 0
        while poll_count < max_polls:
            try:
                response = requests.get(poll_url, headers=headers, timeout=10)
                
                # 处理 429 速率限制
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 2))
                    logger.warning(f"轮询时遇到速率限制，等待 {retry_after} 秒...")
                    time.sleep(retry_after)
                    continue
                
                response.raise_for_status()
                result = response.json()
                
                if result.get("status") == "succeeded":
                    logger.info(f"Replicate 生成完成，轮询次数: {poll_count}")
                    return result
                elif result.get("status") == "failed":
                    error_msg = result.get('error') or result.get('detail') or '未知错误'
                    raise GenerationError(f"Replicate 生成失败: {error_msg}")
                
                # 使用动态间隔，前期更频繁
                if poll_count < 5:
                    time.sleep(0.5)  # 前 5 次每 0.5 秒检查
                else:
                    time.sleep(1)    # 之后每秒检查
                
                poll_count += 1
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"轮询请求失败: {e}")
                time.sleep(2)
                poll_count += 1
        
        raise TimeoutError(f"等待 Replicate 结果超时（{max_polls} 次轮询）")
    
    def _request_stability(self) -> Dict[str, Any]:
        """Stability AI API 请求"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "text_prompts": [{"text": self.prompt}],
            "negative_prompts": [{"text": self.negative_prompt}],
            "cfg_scale": self.guidance,
            "steps": self.steps,
            "width": self.width,
            "height": self.height
        }
        
        if "seed" in self._config and self._config["seed"] >= 0:
            payload["seed"] = self._config["seed"]
        
        response = requests.post(
            self.api_endpoint,
            json=payload,
            headers=headers,
            timeout=self.timeout
        )
        response.raise_for_status()
        
        return response.json()
    
    def _request_huggingface(self) -> Dict[str, Any]:
        """Hugging Face Inference API 请求（使用新的 Router API）"""
        import time
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 使用新的 Router API 格式
        # 从 api_endpoint 提取 model_id
        model_id = self.api_endpoint.split("/models/")[-1] if "/models/" in self.api_endpoint else "runwayml/stable-diffusion-v1-5"
        router_url = f"https://router.huggingface.co/hf-inference/models/{model_id}"
        
        # 检测是否为 FLUX 模型
        is_flux = "flux" in model_id.lower()
        
        # Hugging Face text-to-image 格式
        # 使用 {"inputs": prompt} 格式
        payload = {"inputs": self.prompt}
        
        # 发送请求，带重试逻辑
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                logger.info(f"HuggingFace 请求: {router_url}, 模型: {model_id}, FLUX: {is_flux}")
                
                response = requests.post(
                    router_url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout
                )
                
                # 处理模型加载中（202 Accepted）
                if response.status_code == 202:
                    logger.info("模型正在加载中，等待 10 秒...")
                    time.sleep(10)
                    continue
                
                # 处理速率限制
                if response.status_code == 429:
                    wait_time = 5 * (attempt + 1)
                    logger.warning(f"速率限制，等待 {wait_time} 秒...")
                    time.sleep(wait_time)
                    continue
                
                # 处理 422 错误 - 打印详细错误信息
                if response.status_code == 422:
                    error_detail = response.text[:500]
                    logger.error(f"HF 422 错误详情: {error_detail}")
                    logger.error(f"请求 payload: {payload}")
                
                response.raise_for_status()
                
                # Hugging Face 直接返回图像数据（二进制）
                content_type = response.headers.get('content-type', '')
                logger.info(f"HF 响应类型: {content_type}")
                
                if content_type.startswith('image/'):
                    logger.info("HF 返回图像数据")
                    return {"image_data": response.content}
                else:
                    # 可能是 base64 编码的 JSON
                    result = response.json()
                    logger.info(f"HF 返回 JSON: {type(result)}")
                    return result
                    
            except requests.exceptions.RequestException as e:
                if attempt < max_attempts - 1:
                    wait_time = 5 * (attempt + 1)
                    logger.warning(f"请求失败，{wait_time} 秒后重试: {e}")
                    time.sleep(wait_time)
                else:
                    raise GenerationError(f"HuggingFace 请求失败: {str(e)}")
        
        raise GenerationError("HuggingFace 请求多次重试后仍失败")
    
    def _request_automatic1111(self) -> Dict[str, Any]:
        """AUTOMATIC1111 WebUI API 请求"""
        headers = {"Content-Type": "application/json"}
        
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        payload = {
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "steps": self.steps,
            "cfg_scale": self.guidance,
            "width": self.width,
            "height": self.height,
            "sampler_name": self._config.get("sampler", "DPM++ 2M Karras")
        }
        
        if "seed" in self._config and self._config["seed"] >= 0:
            payload["seed"] = self._config["seed"]
        else:
            payload["seed"] = -1
        
        # ControlNet 支持
        if self._config.get("use_controlnet") and "controlnet_image" in self._config:
            payload["alwayson_scripts"] = {
                "controlnet": {
                    "args": [{
                        "input_image": self._config["controlnet_image"],
                        "model": self._config.get("controlnet_model", "canny"),
                        "weight": self._config.get("controlnet_strength", 1.0)
                    }]
                }
            }
        
        response = requests.post(
            self.api_endpoint,
            json=payload,
            headers=headers,
            timeout=self.timeout
        )
        response.raise_for_status()
        
        return response.json()
    
    def _request_generic(self) -> Dict[str, Any]:
        """通用 API 请求"""
        headers = {"Content-Type": "application/json"}
        
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        payload = {
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "num_inference_steps": self.steps,
            "guidance_scale": self.guidance,
            "width": self.width,
            "height": self.height
        }
        
        if "seed" in self._config and self._config["seed"] >= 0:
            payload["seed"] = self._config["seed"]
        
        response = requests.post(
            self.api_endpoint,
            json=payload,
            headers=headers,
            timeout=self.timeout
        )
        response.raise_for_status()
        
        return response.json()
    
    def _extract_image(self, result: Dict[str, Any]) -> np.ndarray:
        """
        从 API 响应中提取图像
        
        Args:
            result: API 响应
            
        Returns:
            numpy array (RGB)
        """
        api_type = self._detect_api_type()
        
        try:
            if api_type == "replicate":
                # Replicate 返回图像 URL 列表
                output = result.get("output", [])
                if isinstance(output, list) and len(output) > 0:
                    image_url = output[0]
                else:
                    raise GenerationError("Replicate 未返回图像")
                
                img_response = requests.get(image_url, timeout=10)
                img_response.raise_for_status()
                img = Image.open(io.BytesIO(img_response.content))
                
            elif api_type == "stability":
                # Stability AI 返回 base64 编码的图像
                artifacts = result.get("artifacts", [])
                if not artifacts:
                    raise GenerationError("Stability AI 未返回图像")
                
                image_data = base64.b64decode(artifacts[0]["base64"])
                img = Image.open(io.BytesIO(image_data))
                
            elif api_type == "huggingface":
                # Hugging Face 直接返回图像数据
                image_data = result.get("image_data")
                if not image_data:
                    raise GenerationError("Hugging Face 未返回图像")
                
                img = Image.open(io.BytesIO(image_data))
                
            elif api_type == "automatic1111":
                # AUTOMATIC1111 返回 base64 编码的图像
                images = result.get("images", [])
                if not images:
                    raise GenerationError("AUTOMATIC1111 未返回图像")
                
                image_data = base64.b64decode(images[0])
                img = Image.open(io.BytesIO(image_data))
                
            else:
                # 通用处理：尝试多种格式
                # 1. 尝试 base64
                if "image" in result:
                    image_data = base64.b64decode(result["image"])
                    img = Image.open(io.BytesIO(image_data))
                elif "image_base64" in result:
                    image_data = base64.b64decode(result["image_base64"])
                    img = Image.open(io.BytesIO(image_data))
                # 2. 尝试 URL
                elif "image_url" in result:
                    img_response = requests.get(result["image_url"], timeout=10)
                    img_response.raise_for_status()
                    img = Image.open(io.BytesIO(img_response.content))
                elif "output" in result and isinstance(result["output"], list):
                    img_response = requests.get(result["output"][0], timeout=10)
                    img_response.raise_for_status()
                    img = Image.open(io.BytesIO(img_response.content))
                else:
                    raise GenerationError("无法从响应中提取图像")
            
            # 转换为 RGB numpy array
            img_rgb = img.convert("RGB")
            return np.array(img_rgb)
            
        except Exception as e:
            logger.error(f"提取图像失败: {e}")
            raise GenerationError(f"提取图像失败: {str(e)}")
    
    def generate_single(self, seed: Optional[int] = None, **kwargs) -> GenerationResult:
        """
        生成单张图像
        
        Args:
            seed: 随机种子
            
        Returns:
            GenerationResult
        """
        try:
            # 更新种子
            if seed is not None:
                self._config["seed"] = seed
            
            # 发送请求
            start_time = __import__('time').time()
            result = self._make_request()
            api_time = __import__('time').time() - start_time
            
            # 提取图像
            img_array = self._extract_image(result)
            
            # 扩散模型生成的图像通常没有标注框
            # 需要额外调用检测模型或用户手动标注
            annotations = {
                "boxes": [],
                "labels": [],
                "scores": [],
                "metadata": {
                    "prompt": self.prompt,
                    "api_type": self._detect_api_type(),
                    "api_call_time": api_time
                }
            }
            
            return GenerationResult(
                image=img_array,
                annotations=annotations,
                success=True,
                metadata={
                    "api_type": self._detect_api_type(),
                    "api_call_time": api_time,
                    "image_size": {"width": img_array.shape[1], "height": img_array.shape[0]}
                },
                quality_score=0.8  # API 生成图像质量通常较好
            )
            
        except TimeoutError as e:
            logger.error(f"生成超时: {e}")
            return GenerationResult(
                success=False,
                error_message=f"API 请求超时（{self.timeout}秒）"
            )
            
        except Exception as e:
            logger.error(f"生成失败: {e}")
            return GenerationResult(
                success=False,
                error_message=str(e)
            )
    
    def estimate_time(self, count: int) -> float:
        """估算生成时间"""
        # 基于推理步数估算
        # 假设每步 0.1 秒 + 5 秒网络延迟
        time_per_image = self.steps * 0.1 + 5
        return count * time_per_image
