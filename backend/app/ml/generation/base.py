"""
生成器抽象基类

定义所有数据生成器必须实现的接口
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
import numpy as np


class GenerationError(Exception):
    """生成错误异常"""
    pass


@dataclass
class GenerationResult:
    """
    生成结果数据类
    
    Attributes:
        image: 生成的图像 (numpy array, H, W, 3)
        annotations: 标注信息
        success: 是否成功
        error_message: 错误信息（失败时）
        metadata: 额外元数据
        quality_score: 质量分数 (0-1)
    """
    image: Optional[np.ndarray] = None
    annotations: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    quality_score: float = 0.0
    
    def __post_init__(self):
        """确保 annotations 包含必要字段"""
        if 'boxes' not in self.annotations:
            self.annotations['boxes'] = []
        if 'labels' not in self.annotations:
            self.annotations['labels'] = []
        if 'scores' not in self.annotations:
            self.annotations['scores'] = []


class BaseGenerator(ABC):
    """
    数据生成器抽象基类
    
    所有生成器必须实现此接口
    """
    
    # 生成器元数据
    _name: str = ""
    _description: str = ""
    _version: str = "1.0.0"
    _is_builtin: bool = True
    _supported_formats: List[str] = ["yolo", "coco", "voc"]
    
    def __init__(self):
        """初始化生成器"""
        self._config: Dict[str, Any] = {}
        self._initialized: bool = False
    
    @property
    def name(self) -> str:
        """返回生成器名称"""
        return self._name or self.__class__.__name__
    
    @abstractmethod
    def get_name(self) -> str:
        """返回生成器名称（用于前端显示）"""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """返回生成器描述（用于前端显示）"""
        pass
    
    def get_version(self) -> str:
        """返回生成器版本"""
        return self._version
    
    def is_builtin(self) -> bool:
        """是否为内置生成器"""
        return self._is_builtin
    
    @abstractmethod
    def get_config_schema(self) -> Dict[str, Any]:
        """
        返回配置参数的 JSON Schema
        
        前端根据此 Schema 动态渲染配置界面
        
        Returns:
            JSON Schema 对象
            
        Example:
            {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "title": "生成提示词",
                        "description": "描述要生成的缺陷类型"
                    },
                    "num_inference_steps": {
                        "type": "integer",
                        "title": "推理步数",
                        "minimum": 10,
                        "maximum": 100,
                        "default": 50
                    }
                },
                "required": ["prompt"]
            }
        """
        pass
    
    def validate_config(self, config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        验证配置参数
        
        Args:
            config: 用户配置的参数字典
            
        Returns:
            (is_valid, error_message)
        """
        schema = self.get_config_schema()
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        
        # 检查必填字段
        for field_name in required:
            if field_name not in config:
                return False, f"缺少必填字段: {field_name}"
        
        # 验证字段类型和范围
        for key, value in config.items():
            if key not in properties:
                continue  # 允许额外字段
            
            prop = properties[key]
            prop_type = prop.get("type")
            
            # 类型验证
            if prop_type == "string" and not isinstance(value, str):
                return False, f"字段 {key} 必须是字符串"
            elif prop_type == "integer" and not isinstance(value, int):
                return False, f"字段 {key} 必须是整数"
            elif prop_type == "number" and not isinstance(value, (int, float)):
                return False, f"字段 {key} 必须是数字"
            elif prop_type == "boolean" and not isinstance(value, bool):
                return False, f"字段 {key} 必须是布尔值"
            elif prop_type == "array" and not isinstance(value, list):
                return False, f"字段 {key} 必须是数组"
            elif prop_type == "object" and not isinstance(value, dict):
                return False, f"字段 {key} 必须是对象"
            
            # 范围验证
            if prop_type in ("integer", "number"):
                minimum = prop.get("minimum")
                maximum = prop.get("maximum")
                if minimum is not None and value < minimum:
                    return False, f"字段 {key} 不能小于 {minimum}"
                if maximum is not None and value > maximum:
                    return False, f"字段 {key} 不能大于 {maximum}"
            
            # 枚举验证
            enum_values = prop.get("enum")
            if enum_values is not None and value not in enum_values:
                return False, f"字段 {key} 必须是其中之一: {enum_values}"
        
        return True, None
    
    def configure(self, config: Dict[str, Any]) -> None:
        """
        配置生成器参数
        
        Args:
            config: 用户配置的参数字典
            
        Raises:
            ValueError: 参数验证失败
        """
        is_valid, error_msg = self.validate_config(config)
        if not is_valid:
            raise ValueError(f"配置验证失败: {error_msg}")
        
        self._config = config
        self._initialized = True
        self._on_configure(config)
    
    def _on_configure(self, config: Dict[str, Any]) -> None:
        """
        子类可以重写此方法进行额外的配置初始化
        
        Args:
            config: 配置字典
        """
        pass
    
    @abstractmethod
    def generate_single(self, **kwargs) -> GenerationResult:
        """
        生成单张图像
        
        Args:
            **kwargs: 额外参数
            
        Returns:
            GenerationResult 对象
            
        Raises:
            GenerationError: 生成失败
            TimeoutError: 生成超时
        """
        pass
    
    def generate_batch(
        self, 
        count: int, 
        output_dir: str, 
        progress_callback: Optional[callable] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        批量生成图像
        
        Args:
            count: 生成数量
            output_dir: 输出目录
            progress_callback: 进度回调函数(current, total, message)
            **kwargs: 额外参数
            
        Returns:
            {
                "success_count": int,
                "failed_count": int,
                "output_paths": [str, ...],
                "annotations": [dict, ...],
                "quality_scores": [float, ...],
                "errors": [{"image_index": int, "error": str}, ...]
            }
            
        Raises:
            GenerationError: 批量生成失败
        """
        import os
        from pathlib import Path
        
        results = {
            "success_count": 0,
            "failed_count": 0,
            "output_paths": [],
            "annotations": [],
            "quality_scores": [],
            "errors": []
        }
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        for i in range(count):
            try:
                result = self.generate_single(**kwargs)
                
                if result.success and result.image is not None:
                    # 保存图像
                    img_path = output_path / f"generated_{i:05d}.jpg"
                    import cv2
                    cv2.imwrite(str(img_path), cv2.cvtColor(result.image, cv2.COLOR_RGB2BGR))
                    
                    results["success_count"] += 1
                    results["output_paths"].append(str(img_path))
                    results["annotations"].append(result.annotations)
                    results["quality_scores"].append(result.quality_score)
                else:
                    results["failed_count"] += 1
                    results["errors"].append({
                        "image_index": i,
                        "error": result.error_message or "未知错误"
                    })
                
                # 调用进度回调
                if progress_callback:
                    progress_callback(i + 1, count, f"生成图像 {i + 1}/{count}")
                    
            except Exception as e:
                results["failed_count"] += 1
                results["errors"].append({
                    "image_index": i,
                    "error": str(e)
                })
        
        return results
    
    def estimate_time(self, count: int) -> float:
        """
        估算生成指定数量图像的耗时（秒）
        
        Args:
            count: 生成数量
            
        Returns:
            预计耗时（秒）
        """
        # 默认实现：假设每张图像需要 1 秒
        return float(count)
    
    def get_supported_formats(self) -> List[str]:
        """
        返回支持的标注格式
        
        Returns:
            ["yolo", "coco", "voc"] 的子集
        """
        return self._supported_formats.copy()
    
    def get_default_config(self) -> Dict[str, Any]:
        """
        获取默认配置
        
        Returns:
            默认配置字典
        """
        schema = self.get_config_schema()
        properties = schema.get("properties", {})
        
        defaults = {}
        for key, prop in properties.items():
            if "default" in prop:
                defaults[key] = prop["default"]
        
        return defaults
    
    def get_info(self) -> Dict[str, Any]:
        """
        获取生成器信息
        
        Returns:
            生成器信息字典
        """
        return {
            "name": self.get_name(),
            "description": self.get_description(),
            "version": self.get_version(),
            "is_builtin": self.is_builtin(),
            "config_schema": self.get_config_schema(),
            "supported_formats": self.get_supported_formats(),
            "default_config": self.get_default_config()
        }
