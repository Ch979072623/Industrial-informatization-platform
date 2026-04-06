"""
用户相关 Schema
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.security import get_password_hash


class UserBase(BaseModel):
    """用户基础 Schema"""
    username: str = Field(min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(description="邮箱地址")
    
    
class UserCreate(UserBase):
    """用户创建 Schema"""
    password: str = Field(min_length=6, max_length=100, description="密码")
    role: str = Field(default="user", pattern="^(admin|user)$", description="角色")
    production_line_id: Optional[str] = Field(default=None, description="所属产线ID")


class UserUpdate(BaseModel):
    """用户更新 Schema"""
    username: Optional[str] = Field(default=None, min_length=3, max_length=50)
    email: Optional[EmailStr] = Field(default=None)
    password: Optional[str] = Field(default=None, min_length=6, max_length=100)
    role: Optional[str] = Field(default=None, pattern="^(admin|user)$")
    is_active: Optional[bool] = Field(default=None)
    production_line_id: Optional[str] = Field(default=None)


class UserResponse(UserBase):
    """用户响应 Schema"""
    id: str = Field(description="用户ID")
    role: str = Field(description="角色")
    is_active: bool = Field(description="是否激活")
    production_line_id: Optional[str] = Field(description="所属产线ID")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")
    
    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    """用户登录 Schema"""
    username: str = Field(description="用户名")
    password: str = Field(description="密码")


class UserRegister(UserCreate):
    """用户注册 Schema"""
    role: str = Field(default="user", exclude=True)  # 注册时强制为 user 角色
