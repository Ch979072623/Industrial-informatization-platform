"""
Token 相关 Schema
"""
from typing import Optional
from pydantic import BaseModel, Field


class Token(BaseModel):
    """Token 响应 Schema"""
    access_token: str = Field(description="访问令牌")
    refresh_token: str = Field(description="刷新令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(description="过期时间（秒）")


class TokenPayload(BaseModel):
    """Token 载荷 Schema"""
    sub: Optional[str] = Field(default=None, description="用户ID")
    username: Optional[str] = Field(default=None, description="用户名")
    role: Optional[str] = Field(default=None, description="角色")
    production_line_id: Optional[str] = Field(default=None, description="产线ID")
    exp: Optional[int] = Field(default=None, description="过期时间戳")
    type: Optional[str] = Field(default=None, description="令牌类型")


class TokenRefresh(BaseModel):
    """Token 刷新请求 Schema"""
    refresh_token: str = Field(description="刷新令牌")


class TokenRefreshResponse(BaseModel):
    """Token 刷新响应 Schema"""
    access_token: str = Field(description="新的访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(description="过期时间（秒）")
