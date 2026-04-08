"""
生成器注册中心

管理所有可用的数据生成器
"""
from typing import Dict, List, Type, Optional
import logging

from app.ml.generation.base import BaseGenerator

logger = logging.getLogger(__name__)


class GeneratorRegistry:
    """
    生成器注册中心
    
    管理所有可用的数据生成器，提供注册和查询功能
    """
    
    _generators: Dict[str, BaseGenerator] = {}
    _generator_classes: Dict[str, Type[BaseGenerator]] = {}
    
    @classmethod
    def register(cls, generator_class: Type[BaseGenerator]) -> Type[BaseGenerator]:
        """
        注册生成器类
        
        Args:
            generator_class: 生成器类（必须继承 BaseGenerator）
            
        Returns:
            原生成器类（用于装饰器模式）
            
        Example:
            @register_generator
            class MyGenerator(BaseGenerator):
                pass
        """
        try:
            # 创建实例以获取名称
            instance = generator_class()
            name = instance.get_name()
            
            # 检查名称是否已存在
            if name in cls._generator_classes:
                logger.warning(f"生成器 '{name}' 已存在，将被覆盖")
            
            cls._generator_classes[name] = generator_class
            cls._generators[name] = instance
            
            logger.info(f"已注册生成器: {name}")
            return generator_class
            
        except Exception as e:
            logger.error(f"注册生成器失败: {e}")
            raise
    
    @classmethod
    def get_generator(cls, name: str) -> BaseGenerator:
        """
        获取生成器实例
        
        Args:
            name: 生成器名称
            
        Returns:
            生成器实例
            
        Raises:
            ValueError: 生成器不存在
        """
        if name not in cls._generators:
            raise ValueError(f"生成器 '{name}' 不存在。可用生成器: {list(cls._generators.keys())}")
        
        return cls._generators[name]
    
    @classmethod
    def get_generator_class(cls, name: str) -> Type[BaseGenerator]:
        """
        获取生成器类
        
        Args:
            name: 生成器名称
            
        Returns:
            生成器类
            
        Raises:
            ValueError: 生成器不存在
        """
        if name not in cls._generator_classes:
            raise ValueError(f"生成器类 '{name}' 不存在")
        
        return cls._generator_classes[name]
    
    @classmethod
    def create_generator(cls, name: str) -> BaseGenerator:
        """
        创建新的生成器实例
        
        Args:
            name: 生成器名称
            
        Returns:
            新的生成器实例
        """
        generator_class = cls.get_generator_class(name)
        return generator_class()
    
    @classmethod
    def list_generators(cls) -> List[Dict]:
        """
        列出所有可用生成器
        
        Returns:
            生成器信息列表
        """
        return [
            {
                "name": gen.get_name(),
                "description": gen.get_description(),
                "version": gen.get_version(),
                "is_builtin": gen.is_builtin(),
                "config_schema": gen.get_config_schema(),
                "supported_formats": gen.get_supported_formats()
            }
            for gen in cls._generators.values()
        ]
    
    @classmethod
    def list_generator_names(cls) -> List[str]:
        """
        列出所有生成器名称
        
        Returns:
            生成器名称列表
        """
        return list(cls._generators.keys())
    
    @classmethod
    def unregister(cls, name: str) -> bool:
        """
        注销生成器
        
        Args:
            name: 生成器名称
            
        Returns:
            是否成功注销
        """
        if name in cls._generators:
            del cls._generators[name]
            del cls._generator_classes[name]
            logger.info(f"已注销生成器: {name}")
            return True
        return False
    
    @classmethod
    def clear(cls) -> None:
        """清空所有注册器（主要用于测试）"""
        cls._generators.clear()
        cls._generator_classes.clear()
        logger.info("已清空所有生成器注册")
    
    @classmethod
    def is_registered(cls, name: str) -> bool:
        """
        检查生成器是否已注册
        
        Args:
            name: 生成器名称
            
        Returns:
            是否已注册
        """
        return name in cls._generators


# 便捷装饰器
def register_generator(cls: Type[BaseGenerator]) -> Type[BaseGenerator]:
    """
    生成器注册装饰器
    
    用于装饰生成器类，自动注册到注册中心
    
    Example:
        @register_generator
        class MyGenerator(BaseGenerator):
            def get_name(self):
                return "my_generator"
    """
    return GeneratorRegistry.register(cls)


# 延迟导入并注册内置生成器
def register_builtin_generators():
    """注册所有内置生成器"""
    try:
        from app.ml.generation.defect_migration import DefectMigrationGenerator
        GeneratorRegistry.register(DefectMigrationGenerator)
    except Exception as e:
        logger.warning(f"注册 DefectMigrationGenerator 失败: {e}")
    
    try:
        from app.ml.generation.stable_diffusion_api import StableDiffusionAPIGenerator
        GeneratorRegistry.register(StableDiffusionAPIGenerator)
    except Exception as e:
        logger.warning(f"注册 StableDiffusionAPIGenerator 失败: {e}")


# 应用启动时自动注册
def init_generators():
    """初始化所有生成器"""
    register_builtin_generators()
