"""
数据生成模块

提供合成数据生成和缺陷迁移功能
"""

from app.ml.generation.base import BaseGenerator, GenerationError, GenerationResult
from app.ml.generation.registry import GeneratorRegistry, register_generator
from app.ml.generation.defect_migration import DefectMigrationGenerator
from app.ml.generation.stable_diffusion_api import StableDiffusionAPIGenerator

__all__ = [
    "BaseGenerator",
    "GenerationError", 
    "GenerationResult",
    "GeneratorRegistry",
    "register_generator",
    "DefectMigrationGenerator",
    "StableDiffusionAPIGenerator",
]
