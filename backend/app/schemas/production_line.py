"""
产线相关 Schema
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ProductionLineBase(BaseModel):
    """产线基础 Schema"""
    name: str = Field(min_length=1, max_length=100, description="产线名称")
    description: Optional[str] = Field(default=None, description="产线描述")


class ProductionLineCreate(ProductionLineBase):
    """产线创建 Schema"""
    pass


class ProductionLineUpdate(BaseModel):
    """产线更新 Schema"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None)


class ProductionLineResponse(ProductionLineBase):
    """产线响应 Schema"""
    id: str = Field(description="产线ID")
    created_by: str = Field(description="创建者ID")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")
    
    class Config:
        from_attributes = True
