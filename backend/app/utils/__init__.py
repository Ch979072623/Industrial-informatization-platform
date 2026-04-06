"""
工具模块

提供各种实用工具函数和类。
"""

from app.utils.dataset_parser import (
    # 数据类
    BBox,
    DatasetImage,
    DatasetInfo,
    DatasetFormat,
    
    # 解析器
    BaseParser,
    YOLOParser,
    COCOParser,
    VOCParser,
    
    # 转换器
    DatasetConverter,
    
    # 缩略图生成器
    ThumbnailGenerator,
    
    # 统计工具
    DatasetStatistics,
    
    # 异常类
    DatasetParserError,
    InvalidFormatError,
    FileNotFoundError as DatasetFileNotFoundError,
    
    # 便捷函数
    parse_dataset,
    parse_dataset_async,
    convert_dataset,
    convert_dataset_async,
)

__all__ = [
    # 数据类
    "BBox",
    "DatasetImage",
    "DatasetInfo",
    "DatasetFormat",
    
    # 解析器
    "BaseParser",
    "YOLOParser",
    "COCOParser",
    "VOCParser",
    
    # 转换器
    "DatasetConverter",
    
    # 缩略图生成器
    "ThumbnailGenerator",
    
    # 统计工具
    "DatasetStatistics",
    
    # 异常类
    "DatasetParserError",
    "InvalidFormatError",
    "DatasetFileNotFoundError",
    
    # 便捷函数
    "parse_dataset",
    "parse_dataset_async",
    "convert_dataset",
    "convert_dataset_async",
]
