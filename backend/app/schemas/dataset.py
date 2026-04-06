"""
数据集相关 Schema
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class DatasetBase(BaseModel):
    """数据集基础 Schema"""
    name: str = Field(min_length=1, max_length=100, description="数据集名称")
    description: Optional[str] = Field(default=None, description="数据集描述")
    format: str = Field(pattern="^(YOLO|COCO|VOC)$", description="数据格式")
    class_names: List[str] = Field(default_factory=list, description="类别名称列表")
    split_ratio: Dict[str, float] = Field(
        default_factory=lambda: {"train": 0.7, "val": 0.2, "test": 0.1},
        description="数据集划分比例"
    )


class DatasetCreate(DatasetBase):
    """数据集创建 Schema"""
    production_line_id: str = Field(description="所属产线ID")


class DatasetUpdate(BaseModel):
    """数据集更新 Schema"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None)
    class_names: Optional[List[str]] = Field(default=None)
    split_ratio: Optional[Dict[str, float]] = Field(default=None)


class DatasetImageResponse(BaseModel):
    """数据集图像响应 Schema"""
    id: str = Field(description="图像ID")
    filename: str = Field(description="文件名")
    filepath: str = Field(description="文件路径")
    split: str = Field(description="数据划分")
    width: Optional[int] = Field(description="图像宽度")
    height: Optional[int] = Field(description="图像高度")
    annotation_path: Optional[str] = Field(description="标注路径")
    created_at: datetime = Field(description="创建时间")
    
    class Config:
        from_attributes = True


class DatasetResponse(DatasetBase):
    """数据集响应 Schema"""
    id: str = Field(description="数据集ID")
    path: str = Field(description="存储路径")
    total_images: int = Field(description="图像总数")
    production_line_id: str = Field(description="所属产线ID")
    created_by: str = Field(description="创建者ID")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")
    
    class Config:
        from_attributes = True


class DatasetDetailResponse(DatasetResponse):
    """数据集详情响应 Schema"""
    images: List[DatasetImageResponse] = Field(default_factory=list, description="图像列表")
